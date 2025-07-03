import logging
import json
import os

import boto3
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import PromptTemplate

logging.getLogger("langchain_aws.llms.bedrock").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("anthropic").setLevel(logging.WARNING)
logging.getLogger("langchain_aws.chat_models.bedrock").setLevel(logging.WARNING)
logging.getLogger("botocore.credentials").setLevel(logging.WARNING)

# Configure the LLM logger that will log to file.log
llm_logger = logging.getLogger('llm_interactions')
llm_logger.setLevel(logging.INFO)
# Create log file in the same directory as this script
log_file_path = os.path.join(os.path.dirname(__file__), 'file.log')
llm_file_handler = logging.FileHandler(log_file_path)
llm_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
llm_logger.addHandler(llm_file_handler)
llm_logger.propagate = False  # Prevent logs from being sent to the console


rules = """
# Описание игры "Мафия":

Игра проводится с 10 игроками, роли распределяются случайным образом.

В начале игры 3 игрока получают Чёрные карты (1 Дон и 2 Мафии), а 7 игроков получают Красные карты (6 карт Мирных жителей и 1 карта Шерифа).

Одна команда играет против другой.

Три игрока с чёрными картами знают друг друга, а игроки с красными картами не знают, кто красный, а кто чёрный.

Каждый раунд состоит из фаз: "День" и "Ночь".

Во время дневной фазы первый активный игрок может сделать один из следующих ходов:
- Выставить любого живого игрока на голосование для исключения.
- Сказать речь. Речь игрока не больше 130 слов. 

Затем следующий живой игрок делает ход, активные игроки ходят по часовой стрелке.

После дневной фазы, если на голосование выставлено не менее 2 игроков, игроки одновременно голосуют за того, кого они хотят исключить. Затем выбранный игрок исключается из игры и больше не участвует. Если между несколькими игроками возникает ничья, голосование проводится повторно, и если ничья сохраняется во втором голосовании, проводится голосование за исключение всех кандидатов из игры.

Исключенный игрок делает свое последнее заявление (является ли он шерифом и кого проверял) и высказывает свое мнение о других игроках.

Игра начинается с дневной фазы, при этом игрок 1 является текущим игроком.

После дневной фазы наступает ночная фаза, которая начинается с того, что Дон мафии может "убить" любого игрока. Если Дон исключен, решение принимает первая мафия, если первая мафия исключена, решает вторая мафия. Мафия может решить никого не убивать.

Затем Дон проверяет любого другого игрока на предмет того, является ли этот игрок шерифом. Эта информация доступна только Дону и только если Дон жив.

Затем Шериф, если он жив, может проверить любого другого игрока и получит информацию о том, является ли этот игрок мафией или нет.

После ночи убитый игрок может сделать заявление шерифа (если он шериф и кого проверял) и высказать свое мнение.

Затем начинается следующий раунд со следующего неисключенного игрока. Например, игра начинается с игрока 1, если игрок (2) был убит в первую ночь, второй раунд начинается с игрока (3).

Если на любом этапе игры (после голосования или убийства) количество Чёрных игроков равно или превышает количество Красных игроков, это означает победу мафии. Красные игроки побеждают только в том случае, если все чёрные игроки исключены из игры.

Вот объяснение, как может выглядеть игра по ходам:

1. День первого хода, присутствуют 10 игроков - обычно никто не исключается в этом раунде, так как недостаточно информации
2. Ночь первого хода: мафия убивает игрока, остается 9 игроков
3. День второго хода, присутствуют 9 игроков - один игрок выбывает по голосованию
   * Игра всегда продолжается до следующего дня, так как условие победы мафии еще не может быть достигнуто, только один игрок выбывает
4. Ночь второго хода, присутствуют 8 игроков, мафия убивает одного игрока
5. День третьего хода, присутствуют 7 игроков - один игрок выбывает по голосованию
6. Ночь третьего хода, присутствуют 6 игроков, мафия убивает одного игрока
   * Мафия может победить в третью ночь, если два красных игрока уже были исключены голосованием и красный игрок был застрелен ночью
7. День четвертого хода, присутствуют 5 игроков - один игрок выбывает по голосованию
8. Ночь четвертого хода, присутствуют 4 игрока, мафия убивает одного игрока
   * Мафия может победить в четвертом ходу ночью, если два красных игрока уже были исключены голосованием и красный игрок был застрелен ночью
   * Четвертый ход произойдет только если один игрок мафии был исключен (так что после 2 раундов голосования в игре будет 1 или 2 черных игрока и остальные красные)
9. День пятого хода, присутствуют 3 игрока - один игрок выбывает по голосованию
   * Игра заканчивается победой мирных жителей, если мафия была исключена на 5 день, или победой мафии, если был исключен мирный житель
   * На 5-м ходу в игре может присутствовать только 1 мафия. Если присутствует более 2 мафий, то условие победы мафии срабатывает на 4-м ходу ночью; если мафий не осталось, побеждают красные

"""

general_prompt = PromptTemplate.from_template("""Вы игрок в игру Мафия. Правила игры: {rules}
Ваша роль: {role}
Доп информация: {additional}
Позиция за столом: {position}
В игре произошли следующие действия: {player_log}
Ваша очередь сказать речь, не более 130 слов о своих подозрениях, с кем вы играете, куда собираетесь голосовать итп.
""")

action_prompt = PromptTemplate.from_template("""Вы игрок в игру Мафия. Правила игры: {rules}
Ваша роль: {role}
Позиция за столом: {position}
Доп информация: {additional}
В игре произошли следующие действия: {player_log}
Ваша очередь совершить действие.
Доступные действия:
{actions}
ответьте одной цифрой обозначающей какое действие вы предпринимаете.
""")

# Create the original LLM instance
original_llm = ChatAnthropic(model="claude-3-7-sonnet-20250219", max_tokens=3500,
    thinking={"type": "enabled", "budget_tokens": 3000}, max_retries=100)

# Create a wrapper to log the responses
class LoggingLLM:
    def __init__(self, llm_instance):
        self.llm = llm_instance
    
    def invoke(self, messages, **kwargs):
        """
        Invoke the LLM and log the complete response including the thinking block.
        """
        response = self.llm.invoke(messages, **kwargs)
        
        # Log the response, including any thinking block
        try:
            log_data = {
                "llm_response": {
                    "content": response.content,
                    "raw_response": response.raw if hasattr(response, 'raw') else None,
                    "thinking": response.thinking if hasattr(response, 'thinking') else None,
                    "model": response.model if hasattr(response, 'model') else None
                }
            }
            llm_logger.info(f"LLM Response: {json.dumps(log_data, ensure_ascii=False, indent=2)}")
        except Exception as e:
            llm_logger.error(f"Error logging LLM response: {e}")
            # Log the raw response as fallback
            llm_logger.info(f"Raw LLM Response: {response}")
        
        return response
    
    # Proxy other methods
    def __getattr__(self, name):
        return getattr(self.llm, name)

# Use the logging wrapper
llm = LoggingLLM(original_llm)

# Try to read the book file, but handle the case where it doesn't exist
try:
    # Get the project root directory (two levels up from this file)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    book_path = os.path.join(project_root, 'docs', 'book.txt')
    with open(book_path) as book_file:
        book = book_file.readlines()
except FileNotFoundError:
    # If book.txt doesn't exist, use empty book content
    book = ["Book content not available for this game session."]

def create_messages(params, response_type):
    content = []

    content.append({"type": "text",
                    "text": f"Вы профессиональный игрок в игру Мафия. Правила игры: {rules}",
                     "cache_control": {"type": "ephemeral"}})
    
    content.append({"type": "text",
                    "text": f"Для игры можете использовать советы из учебника: {book}",
                     "cache_control": {"type": "ephemeral"}})    
    
    content.append({"type": "text",
                    "text": f"Ваша позиция за столом: {params['position']}",
                     })    

    content.append({"type": "text",
                    "text": f"Ваша роль: {params['role']}",
                     })
    
    content.append({"type": "text",
                    "text": f"Дополнительная информация: {params['additional']}",
                     })
    
    content.append({"type": "text",
                    "text": f"Произошедшие события: ",
                     })    
    
    for log_line in params["player_log"]:
            content.append({"type": "text",
                    "text": f"{log_line}",
                     })
            

    messages = [{"role": "system",
                     "content": content}]
    
    if response_type == 'general':
            messages.append({"role": "user", "content": [{"type": "text",
                "text": "Ваша очередь сказать речь, не более 130 слов о своих подозрениях, с кем вы играете, куда собираетесь голосовать итп."
                    }]})

    if response_type == 'action':
            messages.append({"role": "user", "content": [{"type": "text",
                "text": f"Ваша очередь совершить действие. Доступные действия: {params['actions']} ответьте одной цифрой обозначающей какое действие вы предпринимаете."
                    }]})

    # Log the input parameters to the LLM (excluding book and rules which are cached)
    log_data = {
        "llm_input": {
            "position": params['position'],
            "role": params['role'],
            "additional": params['additional'],
            "player_log": params["player_log"],
            "response_type": response_type
        }
    }
    
    if response_type == 'action':
        log_data["llm_input"]["actions"] = params['actions']
    
    llm_logger.info(f"LLM Input: {json.dumps(log_data, ensure_ascii=False, indent=2)}")

    return messages
