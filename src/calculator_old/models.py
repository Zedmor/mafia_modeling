from collections import defaultdict
from enum import Enum, auto

import numpy as np


class BeliefType(Enum):
    RED = auto()
    BLACK = auto()


class Player:
    def __init__(self, player_id, role=None):
        self.alive = True
        self.player_id = player_id
        self.role = role  # 'Don', 'Mafia', 'Citizen', 'Sheriff', or None if unknown
        self.beliefs = []  # List of Belief instances

    def add_belief(self, belief):
        self.beliefs.append(belief)

    def record_belief(self, target_player, belief_type, belief_strength):
        # Add a new belief to the history using the BeliefType enum
        new_belief = Belief(self.player_id, target_player, belief_type, belief_strength)
        self.add_belief(new_belief)

    def clear(self):
        self.beliefs = []


class Game:
    def __init__(self, players):
        self.players = players  # List of Player instances
        self.day_phase = True  # True if it's day, False if it's night
        self.eliminated_players = []

    def eliminate_player(self, player):
        self.eliminated_players.append(player)


class Belief:
    def __init__(self, source_player, target_player, belief_type, belief_strength):
        self.source_player = source_player  # Player who has the belief
        self.target_player = target_player  # Player the belief is about
        self.belief_type = belief_type  # BeliefType enum
        self.belief_strength = belief_strength  # Confidence level of the belief

    def __repr__(self):
        return (
            f"{self.source_player} -> "
            f"{self.target_player}: {self.belief_type} ({self.belief_strength})"
        )


class BeliefCalculator:
    def __init__(self, game):
        self.game = game
        self.probabilities = {}  # Dictionary to store combined beliefs for each player
        self.decay_factor = 0.5
        self.convergence_threshold = 0.01
        self.max_iterations = 100

    def calculate_probabilities(self):
        # Reset probabilities at the start of calculation
        self.probabilities = {player.player_id: 0 for player in self.game.players}
        belief_counts = {player.player_id: 0 for player in self.game.players}

        # Logic to calculate combined beliefs based on beliefs
        for player in self.game.players:
            for belief in player.beliefs:
                # Update combined belief based on belief strength and type
                if belief.belief_type == BeliefType.RED:
                    self.probabilities[belief.target_player] += belief.belief_strength
                elif belief.belief_type == BeliefType.BLACK:
                    self.probabilities[belief.target_player] -= belief.belief_strength
                belief_counts[belief.target_player] += 1

        # Calculate the average belief for each player
        for player_id in self.probabilities:
            if belief_counts[player_id] > 0:
                self.probabilities[player_id] /= belief_counts[player_id]

        # Clamp combined beliefs to the range [-1, 1]
        for player_id in self.probabilities:
            self.probabilities[player_id] = max(
                min(self.probabilities[player_id], 1), -1
            )

    def update_beliefs(
        self, source_player, target_player, belief_type, belief_strength
    ):
        # Logic to update beliefs after declarations and checks
        source_player.record_belief(target_player, belief_type, belief_strength)
        # Recalculate probabilities after updating beliefs
        self.calculate_probabilities()

    def calculate_player_influence(
        self, player_id, matrix, previous_matrix, sheriff_checks
    ):
        influence_array = np.zeros(matrix.shape[0])
        for other_player_id in range(matrix.shape[0]):
            if player_id == other_player_id or matrix[player_id, other_player_id] <= 0:
                continue  # Skip self-influence and influence from non-trusted players
            if sheriff_checks[player_id, other_player_id]:
                influence_array[other_player_id] = 0  # Skip influence if there's a sheriff check for the target player
            influence = (
                self.decay_factor
                * matrix[player_id, other_player_id]
                * previous_matrix[other_player_id, :]
            )
            influence_array += influence
        return influence_array

    def apply_influence(
        self, player_id, matrix, influence_array, sheriff_checks, updated_matrix
    ):
        updated_matrix[player_id, :] = matrix[player_id, :] + influence_array

        # Apply the constraint that beliefs should not exceed 0.95 in absolute value
        # unless there is a sheriff check
        for i in range(matrix.shape[0]):
            if not sheriff_checks[player_id, i]:
                updated_matrix[player_id, i] = np.clip(updated_matrix[player_id, i], -0.95, 0.95)

        # Normalize the updated beliefs to be within the range [-1, 1]
        non_self_indices = [i for i in range(matrix.shape[0]) if i != player_id]
        max_belief = np.max(np.abs(updated_matrix[player_id, non_self_indices]))
        if max_belief > 1:
            updated_matrix[player_id, non_self_indices] /= max_belief

        for i in non_self_indices:
            if sheriff_checks[player_id, i]:
                updated_matrix[player_id, i] = matrix[player_id, i]

    def check_convergence(self, previous_matrix, updated_matrix):
        return np.all(
            np.abs(previous_matrix - updated_matrix) < self.convergence_threshold
        )

    def update_belief_matrix(self, matrix):
        np.fill_diagonal(matrix, 0)
        updated_matrix = matrix.copy()
        sheriff_checks = np.isin(matrix, [-1, 1])
        converged = False
        iteration = 0

        while not converged and iteration < self.max_iterations:
            iteration += 1
            previous_matrix = updated_matrix.copy()

            for player_id in range(matrix.shape[0]):
                influence_array = self.calculate_player_influence(
                    player_id, matrix, previous_matrix, sheriff_checks
                )
                self.apply_influence(
                    player_id, matrix, influence_array, sheriff_checks, updated_matrix
                )

            converged = self.check_convergence(previous_matrix, updated_matrix)

        np.fill_diagonal(updated_matrix, 1.0)
        np.fill_diagonal(matrix, 1.0)

        return updated_matrix

    def create_belief_matrix(self, game):
        initial_matrix = create_initial_belief_matrix(game)
        updated_matrix = self.update_belief_matrix(initial_matrix)
        return updated_matrix


def create_initial_belief_matrix(game):
    num_players = len(game.players)
    belief_matrix = np.zeros((num_players, num_players))

    # Set self-belief to maximum positive for each player
    np.fill_diagonal(belief_matrix, 1.0)

    # Populate the belief matrix with the weighted beliefs of each player
    for player in game.players:
        # Initialize the total weight and weighted belief sum for normalization
        total_weights = defaultdict(int)
        weighted_belief_sum = defaultdict(int)

        # Apply weights to the beliefs, starting with a weight of 1 for the oldest belief
        weight = defaultdict(lambda: 1)
        for belief in player.beliefs:
            if belief.target_player == player.player_id:
                continue  # Skip self-belief
            belief_value = (
                belief.belief_strength
                if belief.belief_type == BeliefType.RED
                else -belief.belief_strength
            )

            if belief_value == -1 or belief_value == 1:
                # This is a sheriff check, absolute value, we do not use weights
                total_weights[belief.target_player] = 0
                weighted_belief_sum[belief.target_player] = 0

            # Accumulate the weighted belief and total weight
            weighted_belief_sum[belief.target_player] += (
                weight[belief.target_player] * belief_value
            )
            total_weights[belief.target_player] += weight[belief.target_player]
            weight[belief.target_player] += 1  # Increase weight for the next belief

        # Normalize the beliefs about others by the total weight used
        for belief in player.beliefs:
            if total_weights[belief.target_player] > 0:
                if belief.target_player == player.player_id:
                    continue  # Skip self-belief
                # Normalize and update the belief matrix
                belief_matrix[player.player_id, belief.target_player] = (
                    weighted_belief_sum[belief.target_player]
                    / total_weights[belief.target_player]
                )

    return belief_matrix
