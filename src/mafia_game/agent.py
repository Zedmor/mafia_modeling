import re
from abc import ABC
from mafia_game.llm import llm, create_messages
from mafia_game.actions import NullAction

from mafia_game.common import Team
from mafia_game.logger import LogType, file_logger

from mafia_game.logger import logger


def find_first_number_in_range(text, x):
    """
    Find the first instance of a number between 0 and x (inclusive) in a string.

    Args:
        text (str): The input string to search in
        x (int or float): The upper bound of the range

    Returns:
        float or int: The first number found within the range
        None: If no number in the range is found
    """
    # Find all numbers in the string
    numbers = re.findall(r"-?\d+\.?\d*", text)

    # Convert strings to numbers (float or int as appropriate)
    converted_numbers = []
    for num in numbers:
        if "." in num:
            converted_numbers.append(float(num))
        else:
            converted_numbers.append(int(num))

    # Find the first number that is between 0 and x (inclusive)
    for num in converted_numbers:
        if 0 <= num <= x:
            return num

    # Return None if no number is found in the range
    return None


class Agent(ABC):
    def __init__(self, game_state: "CompleteGameState"):
        self.game_state = game_state

    def utterance(self, target_player=None):
        pass

    def select_action(self, actions):
        pass


class HumanAgent(Agent):
    def utterance(self, target_player=None):

        if target_player:
            spearker = self.game_state.game_states[target_player]
        else:
            spearker = self.game_state.current_player

        if target_player is None:
            target_player = self.game_state.active_player

        if spearker.private_data.team == Team.BLACK_TEAM:
            additional_info = f" Ваша мафия: {spearker.private_data.other_mafias}"
        else:
            additional_info = ""

        message = input(
            f"Ваша речь игрок номер {target_player} ({spearker.private_data.role.name}){additional_info}: "
        )
        self.game_state.log(
            f"Речь игрока {target_player}: {message}",
            log_type=LogType.UTTERANCE,
        )

    def select_action(self, actions):
        if all([isinstance(a, NullAction) for a in actions]):
            return actions[0]

        actions_block = {m[0]: str(m[1]) for m in enumerate(actions)}

        print("Возможные действия: ")
        for i, action in actions_block.items():
            print(f"{i}: {action}")

        while True:
            try:
                result = input("Ваш выбор: ")

                return actions[int(result)]
            except ValueError:
                print("Incorrect input. Please try again.")


class LLMAgent(Agent):
    def get_llm_params(self, targer_player=None):
        if not targer_player:
            targer_player = self.game_state.active_player
        role = self.game_state.game_states[targer_player].private_data.role

        text_log = [
                log.message
                for log in self.game_state.game_states[targer_player].private_data.log
            ]
        

        if (
            self.game_state.game_states[targer_player].private_data.team
            == Team.BLACK_TEAM
        ):
            additional = str(
                self.game_state.game_states[targer_player].private_data.other_mafias
            )
        else:
            additional = ""

        return {
            "position": str(targer_player),
            "additional": additional,
            "role": role.name,
            "player_log": text_log
        }

    def utterance(self, target_player=None):

        if target_player:
            spearker = self.game_state.game_states[target_player]
        else:
            spearker = self.game_state.current_player

        if target_player is None:
            target_player = self.game_state.active_player

        params = self.get_llm_params(target_player)
        file_logger.info(f"Invoking with params: {params}")
        response = llm.invoke(create_messages(params, response_type='general'))
        message = response.text()
        self.game_state.log(
            f"Речь игрока {target_player}: {message}",
            log_type=LogType.UTTERANCE,
        )

    def select_action(self, actions):
        if all([isinstance(a, NullAction) for a in actions]):
            return actions[0]

        llm_params = self.get_llm_params()

        actions_block = {m[0]: str(m[1]) for m in enumerate(actions)}

        llm_params["actions"] = str(actions_block)

        while True:
            try:
                file_logger.info(f"Invoking with params: {llm_params}")
                response = llm.invoke(create_messages(llm_params, response_type='action'))

                message = response.text()

                result = find_first_number_in_range(message, len(actions)) or 0

                return actions[int(result)]
            except Exception:
                logger.info("Incorrect input. Please try again.")
