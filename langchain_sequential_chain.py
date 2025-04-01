from langchain_huggingface import ChatHuggingFace, HuggingFacePipeline
from transformers import BitsAndBytesConfig
from langchain_core.messages import (HumanMessage,SystemMessage)
from langchain_core.output_parsers import StrOutputParser
import textwrap  # 공백 제거를 위한 모듈 추가
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_core.prompts import PromptTemplate

##############################################################################################
# 1. LLM 설정: NCSOFT/Llama-VARCO-8B-Instruct
###############################################################################################

# LLM 추론
quantization_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype="float16",
    bnb_4bit_use_double_quant=True,
)

llm = HuggingFacePipeline.from_model_id(
    model_id="NCSOFT/Llama-VARCO-8B-Instruct",
    task="text-generation",
    pipeline_kwargs=dict(
        max_new_tokens=100,  
        do_sample=False,
        repetition_penalty=1.03,
        return_full_text=False,
    ),
    device=0,
    model_kwargs={"quantization_config": quantization_config},
)

chat_model = ChatHuggingFace(llm=llm)

##############################################################################################
# 2. 입력값과 3개의 sub-chain 만들기
###############################################################################################
# 체인을 실행하기 위해서는 query 키를 포함하는 딕셔너리 형태의 데이터를 전달해야 합니다.
input_data = {"query": "나는 슬퍼. 새로산 원피스가 안어울려."}

empathy_description = textwrap.dedent(f"""
    Show empathy for the user's emotions.
    Respond in all answers using informal language (not formal speech).
""")
empathy_chain = ChatPromptTemplate.from_messages([
    SystemMessage(content=empathy_description),
    HumanMessage(content=input_data["query"]) 
]) | chat_model 

question_description = textwrap.dedent(f"""
    Ask specific questions about the user's situation.
    Respond in all answers using informal language (not formal speech).
""")
question_chain = ChatPromptTemplate.from_messages([
    SystemMessage(content=question_description),
    HumanMessage(content=input_data["query"]) 
]) | chat_model 

advice_description = textwrap.dedent(f"""
    Question the user's thoughts and suggest better alternatives.
    Respond in all answers using informal language (not formal speech).
""")
advice_chain = ChatPromptTemplate.from_messages([
    SystemMessage(content=advice_description),
    HumanMessage(content=input_data["query"]) 
]) | chat_model 

##############################################################################################
# 3. 라우트 함수 : 특정 체인으로 분기해줌
###############################################################################################
def route(info):
    # print(f"info: {info}")  # 전달된 데이터 확인
    if "question" in info["topic"].lower():
        print("✅ 선택된 체인: question_chain")
        return question_chain
    elif "advice" in info["topic"].lower():
        print("✅ 선택된 체인: advice_chain")
        return advice_chain
    else:
        print("✅ 선택된 체인: empathy_chain")
        return empathy_chain

# 데이터가 오른쪽으로 체인을 따라 흐른다
# 입력 데이터를 받아 route 함수를 호출하고, 적절한 체인을 선택합니다.
#  이 체인은 Runnable 객체 또는 이를 처리할 수 있는 callable(함수, 람다 함수 등)을 기대합니다.
data = {"topic": lambda x: "advice_chain", "query": lambda x: x["query"]} | RunnableLambda(
    route
)
# lambda x: "reaction"은 입력 데이터를 받아 "reaction" 문자열을 반환합니다.
# "query": lambda x: x["query"]는 나중에 입력될 데이터에서 query 키의 값을 동적으로 가져오는 역할

##############################################################################################
# 4. 특정 말투로 변환하는 체인 추가
###############################################################################################

# 말투 변환 프롬프트 템플릿
tone_prompt = PromptTemplate.from_template("""
아래 문장을 지시사항을 참고하여 애교스러운 말투로 변환해 주세요.    

### 지시사항:  
1. **어미를 부드럽게 늘이기**:  
    - '~지?', '~해줘~', '~잖아~'와 같은 어미를 사용하여 부드럽고 귀여운 느낌을 줍니다.  
2. **감탄사와 생동감 추가**:  
    - '흐응~', '우와~', '응?', '헤헤~', '히히~'와 같은 감탄사나 의성어를 포함하여 생동감을 더합니다.  
3. **애정 어린 호칭 사용**:  
    - 상대방을 '자기야', '애기야', '여보야', '우리 자기~'와 같은 호칭으로 부르며 친밀함을 드러냅니다.  

문장: {response}  

### 변환된 애교 말투:  
애교 말투: 

""")


##############################################################################################
# 5. Sequential 체인 구성
###############################################################################################

# | 연산자를 사용하여 체인을 연결
sequential_chain = (
    data  # 첫 번째 체인: 라우팅
    | RunnableLambda(
        lambda x: (
            print(f"🔍 첫 번째 체인 데이터: {x.content.strip()}"),  # 데이터를 출력
            {"response": x.content.strip()}  # 이후 체인으로 전달할 데이터
        )[1]  # 튜플에서 두 번째 값을 반환
    )
    | tone_prompt  # 두 번째 체인: 일반 프롬프트 템플릿 사용
    | llm  # 일반 언어 모델 호출
)

##############################################################################################
# 6. 체인 실행
###############################################################################################

# 최종적으로 Sequential 체인을 한 번만 실행
final_response = sequential_chain.invoke(input_data)

# 결과 출력
print(f"▶️ 최종 응답 : {final_response}\n")
