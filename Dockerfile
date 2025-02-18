ARG BASE_URL

FROM ${BASE_URL}/library/pytorch:2.1.0-py3.10-cuda11.8.0 AS builder

WORKDIR /workspace
RUN git clone https://github.com/comfyanonymous/ComfyUI.git
WORKDIR /workspace/ComfyUI
RUN python -m venv --system-site-packages /workspace/ComfyUI/venv
ENV PATH="/workspace/ComfyUI/venv/bin:$PATH"
ENV PATH="/root/.local/bin:$PATH"

RUN pip install opencv-python pandas ultralytics py-cpuinfo seaborn thop pytz tzdata matplotlib numexpr httpx[socks] pip-system-certs 
RUN pip install -r requirements.txt
RUN pip install esdk-obs-python --trusted-host pypi.org

WORKDIR /workspace/ComfyUI/custom_nodes
RUN git clone https://github.com/ltdrdata/ComfyUI-Manager.git
RUN git clone https://github.com/AlekPet/ComfyUI_Custom_Nodes_AlekPet.git
RUN git clone https://github.com/twri/sdxl_prompt_styler.git
RUN git clone https://github.com/pythongosssss/ComfyUI-Custom-Scripts.git
RUN git clone https://github.com/cubiq/ComfyUI_IPAdapter_plus.git
RUN git clone https://github.com/ltdrdata/ComfyUI-Impact-Pack.git
RUN git clone https://github.com/Kosinkadink/ComfyUI-Advanced-ControlNet.git

WORKDIR /workspace/ComfyUI/custom_nodes/ComfyUI-Manager
RUN pip install -r requirements.txt

#WORKDIR /workspace/ComfyUI/custom_nodes/ComfyUI-Impact-Pack
#RUN pip install -r requirements.txt && \
#    cd /workspace/ComfyUI/custom_nodes/ComfyUI-Impact-Pack && \
#    /workspace/ComfyUI/venv/bin/python install.py && \
#    cd /workspace/ComfyUI/custom_nodes/ComfyUI-Impact-Pack/impact_subpack && \
#    /workspace/ComfyUI/venv/bin/python install.py


RUN pip install -U spandrel kornia  && pip install argostranslate==1.9.6 ctranslate2==4.3.1 joblib==1.4.2 protobuf==5.27.3 sacremoses==0.0.53 stanza==1.1.1

# Use bash, make nicer
ENV SHELL /bin/bash
# COPY jupyter/bashrc /workspace/.bashrc
WORKDIR /workspace/ComfyUI

FROM ${BASE_URL}/library/pytorch:2.1.0-py3.10-cuda11.8.0 as comfyui

COPY --from=builder /workspace/ComfyUI /workspace/ComfyUI

RUN wget -O /workspace/ComfyUI/models/unet/flux1-schnell.safetensors -c 'https://huggingface.co/black-forest-labs/FLUX.1-schnell/resolve/main/flux1-schnell.safetensors?download=true'

RUN wget -O /workspace/ComfyUI/models/clip/clip_l.safetensors -c 'https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors?download=true'

RUN wget -O /workspace/ComfyUI/models/clip/t5xxl_fp8_e4m3fn.safetensors -c 'https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8_e4m3fn.safetensors?download=true'

RUN wget -O /workspace/ComfyUI/models/vae/ae.safetensors -c 'https://huggingface.co/black-forest-labs/FLUX.1-schnell/resolve/main/ae.safetensors?download=true'

RUN wget -O /workspace/ComfyUI/models/checkpoints/sd_xl_base_1.0.safetensors -c 'https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors?download=true'

RUN wget -O /workspace/ComfyUI/models/vae/sdxl_vae.safetensors -c 'https://huggingface.co/stabilityai/sdxl-vae/resolve/main/sdxl_vae.safetensors?download=true'

RUN wget -O /workspace/ComfyUI/models/vae/sdxl-vae-fp16-fix.safetensors -c 'https://huggingface.co/madebyollin/sdxl-vae-fp16-fix/resolve/main/sdxl_vae.safetensors?download=true'

RUN apt-get update -y && apt-get upgrade -y && apt-get install -y --no-install-recommends openssh-server && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace/ComfyUI

COPY requirements.txt /requirements.txt

RUN /workspace/ComfyUI/venv/bin/python -m pip install -r /requirements.txt

COPY src/ /workspace/ComfyUI_serverless

COPY start.sh /start.sh

RUN chmod 755 /start.sh

CMD ["/start.sh"]