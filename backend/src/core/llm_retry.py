import logging
from tenacity import retry, wait_exponential, stop_after_attempt

logger = logging.getLogger(__name__)


@retry(
    wait=wait_exponential(min=1, max=12),
    stop=stop_after_attempt(3),
    reraise=True,
)
def invoke_llm(llm, prompt):
    return llm.invoke(prompt)
