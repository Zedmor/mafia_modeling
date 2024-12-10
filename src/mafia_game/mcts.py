import logging
import random
import math
import pickle
from mafia_game.game_state import (
    CompleteGameState,
    DayPhase,
    VotingPhase,
    NightKillPhase,
    NightDonPhase,
    NightSheriffPhase,
)
from mafia_game.actions import (
    NominationAction,
    VoteAction,
    KillAction,
    DonCheckAction,
    SheriffCheckAction,
    SheriffDeclarationAction,
)
from mafia_game.common import Role

class Node:
    def __init__(self, state, parent=None, action=None, player_index=None):
        self.state = state
        self.parent = parent
        self.children = []
        self.visits = 0
        self.total_reward = 0.0
        self.untried_actions = state.get_available_actions()
        self.player_index = player_index
        self.action = action
        
    @staticmethod
    def random_choice(actions):
        return random.choice(actions) if actions else None

    def select_child(self, exploration_constant=1.4):
        best_score = -float('inf')
        best_child = None
        for child in self.children:
            exploit = child.total_reward / child.visits
            explore = math.sqrt(2 * math.log(self.visits) / child.visits)
            score = exploit + exploration_constant * explore
            if score > best_score:
                best_score = score
                best_child = child
        return best_child

    def expand(self):
        action = self.untried_actions.pop()
        next_state = self.state.clone()
        next_state.execute_action(action)
        next_state.transition_to_next_phase()
        child_node = Node(
            state=next_state,
            parent=self,
            action=action,
            player_index=next_state.active_player
        )
        self.children.append(child_node)
        return child_node

    def simulate(self):
        current_state = self.state.clone()
        while not current_state.is_terminal():
            action = self.select_simulation_action(current_state)
            if action:
                current_state.current_phase.execute_action(current_state, action)
            current_state.transition_to_next_phase()
        return current_state.get_reward(self.player_index)

    def select_simulation_action(self, state):
        player_index = state.active_player
        player_state = state.game_states[player_index]
        player_role = player_state.private_data.role
        actions = state.get_available_actions()
    
        if isinstance(state.current_phase, DayPhase):
            return self.day_phase_policy(state, actions, player_index, player_role)
        elif isinstance(state.current_phase, VotingPhase):
            return self.voting_phase_policy(state, actions, player_index, player_role)
        elif isinstance(state.current_phase, NightKillPhase):
            return self.night_kill_phase_policy(state, actions, player_index, player_role)
        elif isinstance(state.current_phase, NightDonPhase):
            return self.night_don_phase_policy(state, actions, player_index, player_role)
        elif isinstance(state.current_phase, NightSheriffPhase):
            return self.night_sheriff_phase_policy(state, actions, player_index, player_role)
        else:
            return self.random_choice(actions)

    def day_phase_policy(self, state, actions, player_index, player_role):
        if player_role == Role.SHERIFF:
            if state.turn >= 2 and random.random() < 0.5:
                for action in actions:
                    if isinstance(action, SheriffDeclarationAction) and action.i_am_sheriff:
                        return action
            else:
                for action in actions:
                    if isinstance(action, NominationAction):
                        if self.is_suspicious(state, action.target_player):
                            return action
                return self.random_choice(actions)
        elif player_role in [Role.MAFIA, Role.DON]:
            for action in actions:
                if isinstance(action, NominationAction):
                    if not self.is_team_member(state, action.target_player):
                        return action
            return self.random_choice(actions)
        else:
            for action in actions:
                if isinstance(action, NominationAction):
                    if self.is_suspicious(state, action.target_player):
                        return action
            return self.random_choice(actions)

    def voting_phase_policy(self, state, actions, player_index, player_role):
        for action in actions:
            if isinstance(action, VoteAction):
                if not self.is_team_member(state, action.target_player):
                    return action
        return self.random_choice(actions)

    def night_kill_phase_policy(self, state, actions, player_index, player_role):
        if player_role in [Role.DON, Role.MAFIA]:
            for action in actions:
                if isinstance(action, KillAction):
                    if self.is_dangerous(state, action.target_player):
                        return action
            for action in actions:
                if isinstance(action, KillAction):
                    if not self.is_team_member(state, action.target_player):
                        return action
            return self.random_choice(actions)
        else:
            return None

    def night_don_phase_policy(self, state, actions, player_index, player_role):
        if player_role == Role.DON:
            for action in actions:
                if isinstance(action, DonCheckAction):
                    if self.is_suspicious(state, action.target_player):
                        return action
            return self.random_choice(actions)
        else:
            return None

    def night_sheriff_phase_policy(self, state, actions, player_index, player_role):
        if player_role == Role.SHERIFF:
            for action in actions:
                if isinstance(action, SheriffCheckAction):
                    if self.is_suspicious(state, action.target_player):
                        return action
            return self.random_choice(actions)
        else:
            return None

    def is_suspicious(self, state, player_index):
        return random.random() < 0.3

    def is_team_member(self, state, player_index):
        target_role = state.game_states[player_index].private_data.role
        return target_role in [Role.MAFIA, Role.DON]

    def is_dangerous(self, state, player_index):
        player_state = state.game_states[player_index]
        if player_state.public_data.sheriff_declaration[state.turn]:
            return True
        return False

    def backpropagate(self, reward):
        self.visits += 1
        self.total_reward += reward
        if self.parent:
            self.parent.backpropagate(reward)

    def save(self, filepath):
        with open(filepath, 'wb') as f:
            pickle.dump(self, f)

    @staticmethod
    def load(filepath):
        with open(filepath, 'rb') as f:
            return pickle.load(f)

def mcts_search(root_state, computation_budget):
    root_node = Node(state=root_state)

    for _ in range(computation_budget):
        node = root_node
        # Selection
        while node.untried_actions == [] and node.children != []:
            node = node.select_child()

        # Expansion
        if node.untried_actions:
            node = node.expand()

        # Simulation
        reward = node.simulate()

        # Backpropagation
        node.backpropagate(reward)

    # Choose the action with the highest visit count
    best_child = max(root_node.children, key=lambda c: c.visits)
    return best_child.action
