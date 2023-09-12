from mafia_game.models import (
    Role,
    Player,
    Policy,
    GameState,
    GameController,
    GameActionType,
    GameAction,
    Belief,
)


def test_player_initialization():
    player = Player(1, Role.CITIZEN, Policy.empty())
    assert player.id == 1
    assert player.role == Role.CITIZEN
    assert player.is_alive == True


def test_game_state_initialization():
    players = [Player(i, Role.CITIZEN, Policy.empty()) for i in range(10)]
    game_state = GameState(players)
    assert game_state.day == True
    assert game_state.round == 1
    assert game_state.current_player_index == 0


def test_game_controller_initialization():
    players = [Player(i, Role.CITIZEN, Policy.empty()) for i in range(10)]
    game_state = GameState(players)
    game_controller = GameController(game_state)
    assert game_controller.game_state == game_state


def test_game_action_repr():
    player = Player(1, Role.CITIZEN, Policy.empty())
    game_action = GameAction(GameActionType.DECLARATION, player)
    assert (
        repr(game_action)
        == "Action: [Declaration]: 1 (Citizen) with policy: generic -> None (None)"
    )


def test_game_state_eliminate():
    players = [Player(i, Role.CITIZEN, Policy.empty()) for i in range(10)]
    game_state = GameState(players)
    game_state.eliminate(players[0])
    assert players[0].is_alive == False


def test_game_state_check_end_condition():
    players = [Player(i, Role.CITIZEN, Policy.empty()) for i in range(5)]
    players += [Player(i, Role.MAFIA, Policy.empty()) for i in range(4)]
    game_state = GameState(players)
    assert not game_state.check_end_condition()
    game_state.eliminate(players[0])
    assert game_state.check_end_condition()


def test_game_state_determine_winner():
    players = [Player(i, Role.CITIZEN, Policy.empty()) for i in range(5)]
    players += [Player(i, Role.MAFIA, Policy.empty()) for i in range(4)]
    game_state = GameState(players)
    assert game_state.determine_winner() is None
    for i in range(5):
        game_state.eliminate(players[i])
    assert game_state.determine_winner() is Role.MAFIA


def test_game_state_get_next_alive_player_index():
    players = [Player(i, Role.CITIZEN, Policy.empty()) for i in range(10)]
    game_state = GameState(players)
    assert game_state.get_next_alive_player_index() == 1
    game_state.eliminate(players[0])
    assert game_state.get_next_alive_player_index() == 2


def test_game_state_serialize():
    players = [Player(i, Role.CITIZEN, Policy.empty()) for i in range(10)]
    game_state = GameState(players)
    game_action = GameAction(GameActionType.DECLARATION, players[0])
    game_state.game_actions.append(game_action)
    serialized_actions = game_state.serialize()
    assert serialized_actions == [
        "Action: [Declaration]: 0 (Citizen) with policy: generic -> None (None)"
    ]


def test_game_controller_play_round():
    def declarations_func(game_state, player):
        return []

    def vote_func(game_state, player):
        return None

    def kill_func(game_state, player):
        return None

    def nominate_func(game_state, player):
        return None

    players = [
        Player(i, Role.CITIZEN, Policy(declarations_func, vote_func, kill_func, nominate_func))
        for i in range(10)
    ]
    game_state = GameState(players)
    game_controller = GameController(game_state)
    game_controller.play_round()
    assert game_state.day == False


def test_game_controller_start_game():
    def declarations_func(game_state, player):
        return []

    def vote_func(game_state, player):
        return None

    def kill_func(game_state, player):
        return game_state.players[0] if game_state.players[0].is_alive else None


    def nominate_func(game_state, player):
        return None

    players = [
        Player(i, Role.CITIZEN, Policy(declarations_func, vote_func, kill_func, nominate_func))
        for i in range(5)
    ]
    players += [
        Player(i, Role.MAFIA, Policy(declarations_func, vote_func, kill_func, nominate_func))
        for i in range(5, 10)
    ]
    game_state = GameState(players)
    game_controller = GameController(game_state)
    winner = game_controller.start_game()
    assert winner == Role.MAFIA


def test_player_make_declarations():
    def declarations_func(game_state, player):
        return [(game_state.players[1], Role.MAFIA)]

    players = [
        Player(i, Role.CITIZEN, Policy(declarations_func, None, None, None))
        for i in range(10)
    ]
    game_state = GameState(players)
    players[0].make_declarations(game_state)

    assert len(game_state.game_actions) == 1
    assert game_state.game_actions[0].action_type == GameActionType.DECLARATION
    assert game_state.game_actions[0].player == players[0]
    assert game_state.game_actions[0].target == players[1]
    assert game_state.game_actions[0].belief == Role.MAFIA


def test_player_vote():
    def vote_func(game_state, player):
        return game_state.players[1]

    def nomination_func(game_state, player):
        return game_state.players[1]

    players = [
        Player(i, Role.CITIZEN, Policy(None, vote_func, None, nomination_func)) for i in range(10)
    ]
    game_state = GameState(players)
    players[0].vote(game_state)
    assert len(game_state.game_actions) == 1
    assert game_state.game_actions[0].action_type == GameActionType.VOTE
    assert game_state.game_actions[0].player == players[0]
    assert game_state.game_actions[0].target == players[1]


def test_player_night_action():
    def kill_func(game_state, player):
        return game_state.players[1]

    players = [Player(i, Role.MAFIA, Policy(lambda salf, gs: [], None, kill_func, None)) for i in range(10)]
    game_state = GameState(players)
    players[0].night_action(game_state, None)
    assert len(game_state.game_actions) == 1
    assert game_state.game_actions[0].action_type == GameActionType.KILL
    assert game_state.game_actions[0].player == players[0]
    assert game_state.game_actions[0].target == players[1]
    assert players[1].is_alive == False


def test_game_controller_night_phase():
    def declarations_func(game_state, player):
        return []

    def vote_func(game_state, player):
        return None

    def kill_func(game_state, player):
        return [player for player in game_state.players if player.is_alive][0]

    players = [
        Player(i, Role.MAFIA, Policy(declarations_func, vote_func, kill_func, None))
        for i in range(3)
    ]
    players += [
        Player(i, Role.CITIZEN, Policy(declarations_func, vote_func, kill_func, None))
        for i in range(3, 10)
    ]
    game_state = GameState(players)
    game_controller = GameController(game_state)
    game_controller.night_phase()
    assert players[1].is_alive
    assert len(game_state.game_actions) == 1
    assert game_state.game_actions[0].action_type == GameActionType.KILL
    assert game_state.game_actions[0].player == players[0]
    assert game_state.game_actions[0].target == players[0]
