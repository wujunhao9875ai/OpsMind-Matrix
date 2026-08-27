FROM registry.baidubce.com/paddlepaddle/paddle:2.6.0

# 安装依赖 - 优先使用清华镜像源
RUN pip3 install --default-timeout=300 paddlehub -i https://pypi.tuna.tsinghua.edu.cn/simple || \
    pip3 install --default-timeout=300 paddlehub -i https://mirror.baidu.com/pypi/simple || \
    pip3 install --default-timeout=300 paddlehub

RUN pip3 install --default-timeout=300 paddleocr -i https://pypi.tuna.tsinghua.edu.cn/simple || \
    pip3 install --default-timeout=300 paddleocr -i https://mirror.baidu.com/pypi/simple || \
    pip3 install --default-timeout=300 paddleocr

RUN pip3 install --default-timeout=300 flask -i https://pypi.tuna.tsinghua.edu.cn/simple || \
    pip3 install --default-timeout=300 flask -i https://mirror.baidu.com/pypi/simple || \
    pip3 install --default-timeout=300 flask

COPY server.py /server.py

EXPOSE 8866

CMD ["python3", "/server.py"]