import json
import logging
import os
import uuid
from typing import Any, Dict
from typing import List

from PIL import Image
from spirit_gpu import start, Env

from comfyui_client import ComfyUIClient
import rp_upload


def config_logging():
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[console],
    )


def validate_input(job_input):
    """
    Validates the input for the handler function.

    Args:
        job_input (dict): The input data to validate.

    Returns:
        tuple: A tuple containing the validated data and an error message, if any.
               The structure is (validated_data, error_message).
    """
    # Validate if job_input is provided
    if job_input is None:
        return None, "Please provide input"

    # Check if input is a string and try to parse it as JSON
    if isinstance(job_input, str):
        try:
            job_input = json.loads(job_input)
        except json.JSONDecodeError:
            return None, "Invalid JSON format in input"

    # Validate 'workflow' in input
    workflow = job_input.get("workflow")
    if workflow is None:
        return None, "Missing 'workflow' parameter"

    # Validate 'images' in input, if provided
    images = job_input.get("images")
    if images is not None:
        if not isinstance(images, list) or not all(
            "name" in image and "image" in image for image in images
        ):
            return (
                None,
                "'images' must be a list of objects with 'name' and 'image' keys",
            )

    # Return validated data and no error
    return {"workflow": workflow, "images": images}, None


def to_base64(images: Image.Image):
    import io
    import base64

    im = images.convert("RGB")
    with io.BytesIO() as output:
        im.save(output, format="PNG")
        contents = output.getvalue()
        return base64.b64encode(contents).decode("utf-8")


def process_images(prompt_id: str, data_list: List[str]):
    base64_images = []

    for item in data_list:
        logging.info(f"json load before {item}")
        parsed_data = json.loads(item)
        logging.info(f"json load after {parsed_data}")

        # 检查执行类型并提取图像数据
        if parsed_data.get("type") == "executed" and "output" in parsed_data.get(
            "data", {}
        ):
            output_images = parsed_data["data"]["output"]["images"]

            for img_info in output_images:
                filename = img_info["filename"]
                subfolder = img_info["subfolder"]

                # 构造图像文件的完整路径
                image_path = os.path.join(subfolder, "output", filename)
                logging.info(f"image_path: {image_path}")
                # 打开图像文件并转换为 Base64
                try:
                    with Image.open(image_path) as img:
                        logging.info(f"image open : {img}")

                        if os.environ.get("BUCKET_ENDPOINT_URL", False):
                            base64_str = rp_upload.upload_image(
                                job_id=prompt_id, image_location=image_path
                            )
                        else:
                            base64_str = to_base64(img)
                            base64_images.append(base64_str)
                except Exception as e:
                    print(f"Error processing image {image_path}: {e}")

    return base64_images


def start_handler():
    config_logging()

    def handler(request: Dict[str, Any], _: Env):
        request_input = request.get("input", {})

        # Make sure that the input is valid
        validated_data, error_message = validate_input(request_input)
        if error_message:
            return {"error": error_message}

        client_id = str(uuid.uuid4())
        server_host = os.getenv("COMFYUI_SERVER_HOST", "127.0.0.1")
        server_port = os.getenv("COMFYUI_SERVER_PORT", "8188")
        output_node = request_input.get("output_node", "9")
        secure = request_input.get("secure", False)
        logging.info(f"ip ----------- {server_host}:{server_port}")

        # 实例化ComfyUIClient
        client = ComfyUIClient(
            server_host=server_host,
            server_port=server_port,
            output_node=output_node,
            secure=secure,
        )

        workflow = validated_data.get("workflow")
        images = validated_data.get("images")

        logging.info(f"Received request with prompt: {workflow}")

        # upload images if provided
        upload_result = client.upload_images(client_id, images)
        if upload_result["status"] == "error":
            return upload_result

        # 调用ComfyUIClient生成图片
        try:
            prompt_id = client.queue_prompt(workflow, client_id)
            logging.info(f"Prompt queued with ID: {prompt_id}")

            # 获取生成的图像
            images = client.get_images(client_id=client_id, prompt_id=prompt_id)
            logging.info(f"Generated images for prompt ID {prompt_id}")
            logging.info(f"Generated images data {images}")
            images_base64 = process_images(prompt_id=prompt_id, data_list=images)

            logging.info(f"Generated images base64 data {images_base64}")
            # 返回生成结果
            response = {
                "status": "success",
                "prompt_id": prompt_id,
                "image": images_base64[0],
            }

        except Exception as e:
            logging.error(f"Error generating images: {e}")
            response = {"status": "error", "message": str(e)}
        client.close()
        return response

    return handler


# 启动应用程序
start({"handler": start_handler()})
