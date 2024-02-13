import random

import numpy as np
import torch

from mafia_game.actions import InputTypes
from mafia_game.common import Role, Team
from mafia_game.game_state import (
    CompleteGameState,
    DayPhase,
    EndPhase,
    create_game_state_with_role,
)
from mafia_game.logger import logger
from mafia_game.multihead_nn import select_action

from collections import deque
import random


class ReplayBuffer:
    def __init__(self, capacity):
        self.buffer = deque(maxlen=capacity)

    def push(self, state, action, reward, done, next_state):
        self.buffer.append((state, action, reward, done, next_state))

    def sample(self, batch_size):
        return random.sample(self.buffer, batch_size)

    def __len__(self):
        return len(self.buffer)


def update_q_values(
    red_network, black_network, optimizer, loss_function, experiences, gamma=0.99
):
    # Unpack experiences
    serialized_states, action_data_tuples, rewards, dones, serialized_next_states = zip(
        *experiences
    )

    # Convert serialized states to tensors
    states = torch.tensor(np.array(serialized_states), dtype=torch.float32)
    rewards = torch.tensor(rewards, dtype=torch.float32)
    next_states = torch.tensor(np.array(serialized_next_states), dtype=torch.float32)
    dones = torch.tensor(dones, dtype=torch.float32)

    # Initialize lists to store current and target Q-values
    current_q_values_list = []
    target_q_values_list = []
    loss_list = []

    # Loop through each experience
    for state, action_data_tuple, reward, next_state, done in zip(
        states, action_data_tuples, rewards, next_states, dones
    ):
        action_type, action_data = action_data_tuple
        deserialized_state = CompleteGameState.deserialize(state.numpy())
        player_index = deserialized_state.active_player
        deserialized_next_state = CompleteGameState.deserialize(next_state.numpy())
        player_state = deserialized_state.game_states[player_index]

        if player_state.private_data.role in (Role.MAFIA, Role.DON):
            network = black_network
        else:
            network = red_network

        action_type_index = network.action_types.index(action_type)

        mask1 = action_type.generate_action_mask(deserialized_state, player_index)
        mask2 = action_type.generate_action_mask(deserialized_next_state, player_index)
        # Get outputs for all actions using training mode
        current_outputs = network(deserialized_state, action_type_index, mask1)
        next_outputs = network(deserialized_next_state, action_type_index, mask2)

        # Select the Q-value for the action taken
        if action_type.input_type == InputTypes.INDEX:
            action_data_tensor = torch.tensor([action_data], dtype=torch.int64)
            current_q_values = current_outputs.gather(
                1, action_data_tensor.unsqueeze(1)
            )
            current_q_values_list.append(current_q_values)
        elif action_type.input_type == InputTypes.VECTOR:
            # For VECTOR input type, the action_data is the entire belief vector
            # Reshape current_outputs to match the shape expected by the normalize_vector function
            reshaped_current_outputs = current_outputs.view(-1, 10, 3)
            # Normalize the output to represent a probability distribution for each player
            current_beliefs = torch.nn.functional.softmax(
                reshaped_current_outputs, dim=2
            )
            # Assuming action_data is the target belief vector
            # Convert action_data to a tensor and reshape it to match the current_beliefs shape
            target_beliefs = torch.tensor(action_data, dtype=torch.int64).view(-1, 10)
            # Calculate the cross-entropy loss for each belief vector
            # Cross-entropy loss expects a long tensor of class indices for the target
            belief_loss = torch.nn.functional.cross_entropy(
                current_beliefs.view(-1, 3), target_beliefs.view(-1), reduction="none"
            )
            # Reshape belief_loss back to the batch shape and store for later aggregation
            belief_loss = belief_loss.view(-1, 10).mean(
                dim=1
            )  # Take the mean loss across all players
            loss_list.append(belief_loss)

        # Compute the target Q-value for INDEX type actions
        if action_type.input_type == InputTypes.INDEX:
            if done:
                target_q_values = reward
            else:
                # Get the maximum Q-value for the next state
                max_next_q_values = next_outputs.max(1)[0]
                # Compute the target Q-value using the Bellman equation
                target_q_values = reward + (gamma * max_next_q_values)

            target_q_values_list.append(target_q_values)
            # Store the current and target Q-values

    current_q_values = (
        torch.cat(current_q_values_list).squeeze(1)
        if current_q_values_list
        else torch.tensor([])
    )
    all_losses = torch.cat(loss_list) if loss_list else torch.tensor([])
    # Compute the loss for INDEX type actions
    if target_q_values_list:
        target_q_values = torch.cat(target_q_values_list)
        mask = (current_q_values != -float("inf")) & (target_q_values != -float("inf"))
        index_loss = loss_function(current_q_values[mask], target_q_values[mask])
        all_losses = (
            torch.cat([all_losses, index_loss.unsqueeze(dim=0)])
            if all_losses.numel()
            else index_loss
        )

    total_loss = all_losses.mean()

    # Perform gradient descent
    optimizer.zero_grad()
    total_loss.backward()
    optimizer.step()

    resulting_loss = total_loss.item()

    with open(
        "/home/ANT.AMAZON.COM/zedmor/PycharmProjects/mafia_modeling/src/mafia_game/logs/loss_file.log",
        "a",
    ) as loss_file:
        loss_file.write(f"LOSS: {resulting_loss}\n")

    return resulting_loss


def train(
    red_network,
    black_network,
    red_optimizer,
    black_optimizer,
    loss_function,
    num_episodes,
    gamma=0.99,
    replay_buffer_size=10000,
    batch_size=64,
):
    replay_buffer = ReplayBuffer(replay_buffer_size)

    for episode in range(num_episodes):
        game_states = [
            create_game_state_with_role(r)
            for r in [Role.CITIZEN] * 6 + [Role.SHERIFF] + [Role.MAFIA] * 2 + [Role.DON]
        ]
        random.shuffle(game_states)

        mafia_player_indexes = [
            i
            for i in range(10)
            if game_states[i].private_data.role in (Role.MAFIA, Role.DON)
        ]

        for mafia_player in mafia_player_indexes:
            game_states[mafia_player].private_data.other_mafias.other_mafias = np.array(
                mafia_player_indexes
            )

        game = CompleteGameState(
            game_states=game_states,
            current_phase=DayPhase(),
            active_player=0,
            turn=0,
            team_won=Team.UNKNOWN,
        )
        logger.info("=================== NEW GAME ====================")
        logger.info(f"Starting turn {game.turn}")

        stringbuilder = ""
        for i, state in enumerate(game.game_states):
            stringbuilder += (
                f"{i}: Alive: {state.alive}, Role: {state.private_data.role} | "
            )

        logger.info(stringbuilder)

        logger.info(f"First player {game.active_player}")

        red_states = []
        black_states = []

        # Run the game until it is completed
        while game.team_won == Team.UNKNOWN:
            started_player = game.active_player
            while True:
                allowed_actions = game.get_available_action_classes()
                player_state = game.game_states[game.active_player]

                is_black_player = player_state.private_data.team == Team.BLACK_TEAM

                is_red_player = not is_black_player

                if is_black_player:
                    optimizer = black_optimizer
                    network = black_network
                else:
                    optimizer = red_optimizer
                    network = red_network

                if player_state.alive:
                    for action_type in allowed_actions:
                        action, action_data = select_action(
                            network, game, action_type, game.active_player
                        )
                        if action:
                            old_state = game.deserialize(game.serialize())
                            logger.info(action)
                            game.execute_action(action)
                            game.check_end_conditions()
                            reward = calculate_reward(game, game.active_player)

                            if is_red_player:
                                if not red_states:
                                    red_states = [
                                        old_state.serialize(),
                                        (action_type, action_data),
                                        reward,
                                        int(game.team_won != Team.UNKNOWN),
                                    ]
                                else:
                                    # Use current reward as well
                                    red_states[-2] = red_states[-2] + reward * 0.99
                                    replay_buffer.push(*red_states, game.serialize())
                                    red_states = []

                            if is_black_player:
                                if not black_states:
                                    black_states = [
                                        old_state.serialize(),
                                        (action_type, action_data),
                                        reward,
                                        int(game.team_won != Team.UNKNOWN),
                                    ]
                                else:
                                    black_states[-2] = black_states[-2] + reward * 0.99
                                    replay_buffer.push(*black_states, game.serialize())
                                    black_states = []

                            if len(replay_buffer) > batch_size:
                                experiences = replay_buffer.sample(batch_size)
                                update_q_values(
                                    red_network,
                                    black_network,
                                    optimizer,
                                    loss_function,
                                    experiences,
                                    gamma,
                                )
                game.check_end_conditions()
                while True and game.team_won == Team.UNKNOWN:
                    game.active_player += 1
                    if game.active_player > 9:
                        game.active_player = 0
                    if game.game_states[game.active_player].alive:
                        break

                if (
                    game.active_player == started_player
                    or game.team_won != Team.UNKNOWN
                ):
                    break

            game.active_player = started_player
            game.transition_to_next_phase()
            if isinstance(game.current_phase, DayPhase):
                logger.info("==============================")
                logger.info(f"Starting turn {game.turn}")
                stringbuilder = ""
                for i, state in enumerate(game.game_states):
                    if state.alive:
                        stringbuilder += f"{i}: Role: {state.private_data.role} | "

                logger.info(stringbuilder)
                logger.info(f"First player {game.active_player}")

        # Check that the game has a winner
        assert game.team_won in [Team.RED_TEAM, Team.BLACK_TEAM]
        logger.info(f"Won: {game.team_won}")
        logger.info("=================== END OF THE GAME =============================")


def calculate_reward(game_state, player_index):
    # Reward is given at the end of the game
    if isinstance(game_state.current_phase, EndPhase):
        if (
            game_state.team_won
            == game_state.game_states[player_index].private_data.team
        ):
            return 1  # Reward for winning
    return 0  # No reward if the game is not over or if the player's team did not win
