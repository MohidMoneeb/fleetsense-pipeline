FROM public.ecr.aws/lambda/python:3.12

COPY requirements.txt ${LAMBDA_TASK_ROOT}
RUN pip install --no-cache-dir -r requirements.txt \
 && find /var/lang /var/task -depth -type d -name "nvidia*" -exec rm -rf {} + 2>/dev/null; true

COPY app.py rul_model.json feature_meta.json ${LAMBDA_TASK_ROOT}/

CMD [ "app.handler" ]
