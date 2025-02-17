import logging
import uuid
import websocket
import requests
import json
import urllib.request
import urllib.parse
import base64
from io import BytesIO
from requests.adapters import HTTPAdapter

# YOU MUST IGNORE THE rETRY MODULE IMPORT ERROR
from requests.packages.urllib3.util.retry import Retry  # type: ignore


class ComfyUIClient:
    def __init__(
        self, server_host: str, server_port: str, output_node: str, secure: bool = False
    ) -> None:
        self.ready = False
        # self.server_address = server_addr
        self.server_host = server_host
        self.server_port = server_port
        self.secure = secure
        self.output_node = output_node
        self.ws = websocket.WebSocket()
        logging.info(
            f"ComfyUIClient created with server address {self.server_host}:{self.server_port}"
        )

    def _get_base_url(self):
        scheme = "https" if self.secure is True else "http"
        return f"{scheme}://{self.server_host}:{self.server_port}"

    def queue_prompt(self, prompt, client_id: str) -> str:

        self.ws.connect(
            f'{"wss" if self.secure else "ws"}://{self.server_host}:{self.server_port}/ws?clientId={client_id}'
        )
        self.check_ready()
        p = {"prompt": prompt, "client_id": client_id}
        data = json.dumps(p).encode("utf-8")
        req = urllib.request.Request(f"{self._get_base_url()}/prompt", data=data)
        return json.loads(urllib.request.urlopen(req).read())["prompt_id"]

    def upload_image(self, client_id, image) -> str:
        self.check_ready()
        filename = str(uuid.uuid4())
        data = {
            "image": (filename, open(image, "rb")),
        }
        resp = requests.post(
            f"{self._get_base_url()}/upload/image?client_id={client_id}", files=data
        )
        if resp.status_code != 200:
            raise Exception(
                f"Failed to upload image to server {self.server_host}:{self.server_port}, files{data}: {resp.text}"
            )

        result = resp.json()
        return (
            f'{result["subfoler"]}/{result["name"]}'
            if "subfoler" in result and result["subfolder"] is not None
            else result["name"]
        )

    def upload_images(self, client_id, images):
        """
        Upload a list of base64 encoded images to the ComfyUI server using the /upload/image endpoint.

        Args:
            client_id (str): The client ID for the ComfyUI server.
            images (list): A list of dictionaries, each containing the 'name' of the image and the 'image' as a base64 encoded string.
            server_address (str): The address of the ComfyUI server.

        Returns:
            list: A list of responses from the server for each image upload.
        """

        if not images:
            return {
                "status": "success",
                "message": "No images provided",
                "details": [],
            }

        responses = []
        upload_errors = []

        logging.info(f"Uploading {len(images)} images to the server")

        self.check_ready()
        for image in images:
            name = image["name"]
            image_data = image["image"]
            blob = base64.b64decode(image_data)

            # prepare the form dara
            files = {
                "image": (name, BytesIO(blob), "image/png"),
                "overwrite": (None, "true"),
            }

            # POST request to upload the image
            response = requests.post(
                f"{self._get_base_url()}/upload/image?client_id={client_id}",
                files=files,
            )

            if response.status_code != 200:
                upload_errors.append(f"Failed to upload image {name}: {response.text}")
            else:
                responses.append(f"successfully uploaded {name}")

        if upload_errors:
            logging.error(f"Failed to upload some images: {upload_errors}")
            return {
                "status": "error",
                "message": "Failed to upload some images",
                "details": upload_errors,
            }

        logging.info(f"Successfully uploaded {len(responses)} images")

        return {
            "status": "success",
            "message": "All images uploaded successfully",
            "details": responses,
        }

    def get_images(self, client_id: str, prompt_id: str):
        self.check_ready()
        output_images = {}
        current_node = ""
        logging.info(f"is here1 {self.output_node} {client_id} {prompt_id}")
        try:
            while True:
                out = self.ws.recv()
                logging.info(f"Received data: {out} (type: {type(out)})")
                logging.info(f"current node {current_node}")
                if isinstance(out, str):
                    message = json.loads(out)
                    if (
                        message["type"] == "executed"
                        and message["data"]["node"] == self.output_node
                    ):
                        logging.info(f"is here6{current_node} {out}")
                        images_output = output_images.get(self.output_node, [])
                        images_output.append(out)
                        output_images[self.output_node] = images_output
                    if message["type"] == "executing":
                        data = message["data"]
                        if data["prompt_id"] == prompt_id:
                            if data["node"] is None:
                                break  # Execution is done
                            else:
                                current_node = data["node"]
        finally:
            self.ws.close()
            logging.info(f"WebSocket closed.")

        logging.info(f"is here2{output_images}")
        return output_images[self.output_node]

    def check_ready(self) -> bool:
        logging.info(
            f"Checking ComfyUI server status: {self.ready} at {self._get_base_url()}"
        )
        if self.ready is True:
            return True
        try:
            logging.info(
                f"Begin to detectet the ComfyUI server {self._get_base_url()}is ready"
            )
            resp = requests_retry_session().get(f"{self._get_base_url()}/system_stats")
            if resp.status_code >= 300:
                logging.error(
                    f"Failed to get system stats from server {self._get_base_url()}: {resp.text}"
                )
                return False
            else:
                logging.info("ComfyUI server is ready")
                self.ready = True
        except Exception as e:
            logging.exception(
                f"Exception occurred while detecting ComfyUI server status at {self._get_base_url()}: {e}"
            )
            raise Exception(
                f"Failed to detect ComfyUI server status at {self._get_base_url()}"
            )

        return self.ready

    def close(self):
        if self.ws is not None:
            self.ws.close()


def requests_retry_session(
    retries=10,
    backoff_factor=0.1,
    status_forcelist=(500, 502, 504),
    session=None,
):
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


# deprecated
def detect_comfyui_status(server_address: str, secure: bool = False) -> bool:
    resp = requests.get(
        f'{"https" if secure is True else "http"}://{server_address}/system_stats'
    )
    logging.info(f"Checking comfyui status: {resp.status_code} at {server_address}")
    if resp.status_code >= 300:
        raise Exception(
            f"Failed to get system stats from server {server_address}: {resp.text}"
        )
    return True
