import numpy as np
import pytest

from mafia_game.common import Check
from mafia_game.game_state import (
    ARRAY_SIZE,
    Checks,
    GameState,
    MAX_TURNS,
    PrivateData,
    PublicData,
    Role,
    Team,
    Beliefs,
    Votes,
    Kills,
    Nominations,
    Booleans,
    CompleteGameState,
    )


def test_sheriff_check_initialization():
    check = Check()
    assert isinstance(check.checks, np.ndarray)
    assert check.checks.size == 10
    assert np.all(check.checks == 0)


def test_sheriff_checks_initialization():
    checks = Checks()
    assert checks.checks.size == 10
    assert all(isinstance(check, Check) for check in checks.checks)


def test_sheriff_checks_add_check():
    checks = Checks()
    check = Check()
    checks.add_check(check)
    assert checks.checks[0] is check
    assert checks._next_index == 1


def test_sheriff_checks_add_check_full():
    checks = Checks()
    for _ in range(10):
        checks.add_check(Check())
    with pytest.raises(ValueError):
        checks.add_check(Check())


def test_sheriff_checks_add_check_wrong_type():
    checks = Checks()
    with pytest.raises(ValueError):
        checks.add_check(object())  # Trying to add an object that is not a SheriffCheck


def test_sheriff_checks_serialize_empty():
    checks = Checks()
    serialized = checks.serialize()
    assert isinstance(serialized, np.ndarray)
    assert serialized.size == 100
    assert np.all(serialized == 0)


def test_sheriff_checks_serialize_partial():
    checks = Checks()
    checks.add_check(Check())
    serialized = checks.serialize()
    assert isinstance(serialized, np.ndarray)
    assert serialized.size == 100
    assert np.all(serialized[:10] == 0)  # First check is zeros
    assert np.all(serialized[10:] == 0)  # Rest are zeros


def test_sheriff_checks_serialize_full():
    checks = Checks()
    for _ in range(10):
        checks.add_check(Check())
    serialized = checks.serialize()
    assert isinstance(serialized, np.ndarray)
    assert serialized.size == 100
    assert np.all(serialized == 0)  # All checks are zeros


# Test initialization of GameState
def test_game_state_initialization():
    private_data = PrivateData(role=Role.CITIZEN)
    public_data = PublicData()
    game_state = GameState(private_data=private_data, public_data=public_data)
    assert game_state.alive


# Test serialization of GameState
def test_game_state_serialization():
    private_data = PrivateData(role=Role.CITIZEN)
    public_data = PublicData()
    game_state = GameState(private_data=private_data, public_data=public_data)
    serialized_state = game_state.serialize()
    assert isinstance(serialized_state, np.ndarray)
    # The size should be the sum of all serialized components plus turn and team_won
    expected_size = (
        (10 * 10)
        + (10 * 10)  # sheriff_checks
        + (10 * 10)  # don_checks
        + (10 * 10)  # beliefs
        + (10 * 10)  # nominations
        + 10  # votes
        + (10 * 10)  # sheriff_declaration
        + (10 * 10)  # public_sheriff_checks
        + 1  # kills
        + 1  # Alive or dead?
        + 3  # Other mafias indexes
    )

    assert serialized_state.size == expected_size


# Test setting the winner in GameState
def test_game_state_set_winner():
    private_data = PrivateData(role=Role.CITIZEN)
    public_data = PublicData()
    game_state = GameState(private_data=private_data, public_data=public_data)
    game_state.set_winner(Team.RED_TEAM)
    assert game_state.team_won == Team.RED_TEAM


# Test setting an invalid winner in GameState
def test_game_state_set_winner_invalid():
    private_data = PrivateData(role=Role.CITIZEN)
    public_data = PublicData()
    game_state = GameState(private_data=private_data, public_data=public_data)
    with pytest.raises(ValueError):
        game_state.set_winner("invalid")  # Passing an invalid team


# Test the default factory for Checks in PublicData
def test_public_data_checks_default_factory():
    public_data = PublicData()
    assert isinstance(public_data.beliefs, Beliefs)
    assert isinstance(public_data.votes, Votes)
    assert isinstance(public_data.kills, Kills)
    assert isinstance(public_data.nominations, Nominations)
    assert isinstance(public_data.sheriff_declaration, Booleans)
    assert isinstance(public_data.public_sheriff_checks, Checks)


# Test the default factory for Checks in PrivateData
def test_private_data_checks_default_factory():
    private_data = PrivateData(role=Role.CITIZEN)
    assert isinstance(private_data.sheriff_checks, Checks)
    assert isinstance(private_data.don_checks, Checks)


# Helper function to create a serialized state with a specific role and team_won
def create_serialized_state_with_role_and_winner(role: Role, team_won: Team):
    serialized_state = np.zeros(ARRAY_SIZE)  # Updated size
    serialized_state[0] = role.value
    return serialized_state


@pytest.mark.parametrize(
    "role, team_won",
    [
        (Role.CITIZEN, Team.RED_TEAM),
        (Role.SHERIFF, Team.BLACK_TEAM),
        (Role.MAFIA, Team.RED_TEAM),
        (Role.DON, Team.BLACK_TEAM),
    ],
)
def test_game_state_deserialization(role, team_won):
    serialized_state = create_serialized_state_with_role_and_winner(role, team_won)
    game_state = GameState.deserialize(serialized_state)
    assert game_state.private_data.role == role
    assert not game_state.alive


# Test deserialization with an incorrect size array
def test_game_state_deserialization_incorrect_size():
    serialized_state = np.zeros(700)  # Incorrect size
    with pytest.raises(IndexError):
        GameState.deserialize(serialized_state)


# Test round-trip serialization and deserialization
def test_game_state_serialization_deserialization_round_trip():
    # Create a game state with some data
    private_data = PrivateData(role=Role.SHERIFF)
    public_data = PublicData()
    game_state = GameState(
        private_data=private_data,
        public_data=public_data,
    )

    # Manually populate some checks for testing
    for i in range(MAX_TURNS):
        sheriff_check = Check()
        sheriff_check.checks[i] = 1  # Set some data
        private_data.sheriff_checks.add_check(sheriff_check)

    # Serialize the game state
    serialized_state = game_state.serialize()

    # Deserialize it back into a game state
    deserialized_game_state = GameState.deserialize(serialized_state)

    # Verify that the deserialized game state matches the original
    assert deserialized_game_state.private_data.role == game_state.private_data.role

    for i in range(MAX_TURNS):
        assert np.array_equal(
            deserialized_game_state.private_data.sheriff_checks.checks[i].checks,
            game_state.private_data.sheriff_checks.checks[i].checks,
        )


# Helper function to generate a random Checks object
def generate_random_checks(max_value=3):
    checks = Checks()
    for _ in range(MAX_TURNS):
        check = Check()
        check.checks = np.random.randint(0, max_value + 1, size=MAX_TURNS)
        checks.add_check(check)
    return checks


# Helper function to generate a random Booleans object
def generate_random_booleans():
    booleans = Booleans()
    booleans.values = np.random.randint(
        0, 2, size=MAX_TURNS
    )  # Only 0 or 1 for boolean values
    return booleans


# Test serialization and deserialization of sheriff checks
def test_sheriff_checks_serialization_deserialization():
    original_checks = generate_random_checks()
    serialized_checks = original_checks.serialize()
    deserialized_checks = Checks.deserialize(serialized_checks)
    assert np.array_equal(original_checks.serialize(), deserialized_checks.serialize())


# Test serialization and deserialization of don checks
def test_don_checks_serialization_deserialization():
    original_checks = generate_random_checks()
    serialized_checks = original_checks.serialize()
    deserialized_checks = Checks.deserialize(serialized_checks)
    assert np.array_equal(original_checks.serialize(), deserialized_checks.serialize())


# Test serialization and deserialization of beliefs
def test_beliefs_serialization_deserialization():
    original_beliefs = generate_random_checks()
    serialized_beliefs = original_beliefs.serialize()
    deserialized_beliefs = Checks.deserialize(serialized_beliefs)
    assert np.array_equal(
        original_beliefs.serialize(), deserialized_beliefs.serialize()
    )


# Test serialization and deserialization of nominations
def test_nominations_serialization_deserialization():
    original_nominations = generate_random_checks()
    serialized_nominations = original_nominations.serialize()
    deserialized_nominations = Checks.deserialize(serialized_nominations)
    assert np.array_equal(
        original_nominations.serialize(), deserialized_nominations.serialize()
    )


# Test serialization and deserialization of votes
def test_votes_serialization_deserialization():
    original_votes = generate_random_checks()
    serialized_votes = original_votes.serialize()
    deserialized_votes = Checks.deserialize(serialized_votes)
    assert np.array_equal(original_votes.serialize(), deserialized_votes.serialize())


# Test serialization and deserialization of sheriff declarations
def test_sheriff_declarations_serialization_deserialization():
    original_declarations = generate_random_booleans()
    serialized_declarations = original_declarations.values
    deserialized_declarations = Booleans.deserialize(serialized_declarations)
    assert np.array_equal(
        original_declarations.values, deserialized_declarations.values
    )


# Test serialization and deserialization of kills
def test_kills_serialization_deserialization():
    original_kills = generate_random_checks()
    serialized_kills = original_kills.serialize()
    deserialized_kills = Checks.deserialize(serialized_kills)
    assert np.array_equal(original_kills.serialize(), deserialized_kills.serialize())


def generate_random_booleans():
    booleans = Booleans()
    booleans.values = np.random.randint(
        0, 2, size=MAX_TURNS
    )  # Only 0 or 1 for boolean values
    return booleans


# Test serialization and deserialization of the entire GameState
def test_game_state_serialization_deserialization():
    # Create a random GameState object
    private_data = PrivateData(
        role=np.random.choice(list(Role)),
        sheriff_checks=generate_random_checks(len(Team)),
        don_checks=generate_random_checks(1),
    )
    public_data = PublicData(
        beliefs=generate_random_checks(len(Team)),
        nominations=generate_random_checks(1),
        votes=generate_random_checks(1),
        sheriff_declaration=generate_random_booleans(),
        public_sheriff_checks=generate_random_checks(1),
        kills=generate_random_checks(1),
    )
    game_state_1 = GameState(
        private_data=private_data,
        public_data=public_data,
    )

    # Serialize the GameState object
    serialized_state = game_state_1.serialize()

    # Deserialize the array to create another GameState object
    game_state_2 = GameState.deserialize(serialized_state)

    # Verify that the two GameState objects are equivalent
    assert game_state_1.private_data.role == game_state_2.private_data.role
    assert np.array_equal(
        game_state_1.private_data.sheriff_checks.serialize(),
        game_state_2.private_data.sheriff_checks.serialize(),
    )
    assert np.array_equal(
        game_state_1.private_data.don_checks.serialize(),
        game_state_2.private_data.don_checks.serialize(),
    )
    assert np.array_equal(
        game_state_1.public_data.beliefs.serialize(),
        game_state_2.public_data.beliefs.serialize(),
    )
    assert np.array_equal(
        game_state_1.public_data.nominations.serialize(),
        game_state_2.public_data.nominations.serialize(),
    )
    assert np.array_equal(
        game_state_1.public_data.votes.serialize(),
        game_state_2.public_data.votes.serialize(),
    )
    assert np.array_equal(
        game_state_1.public_data.sheriff_declaration.values,
        game_state_2.public_data.sheriff_declaration.values,
    )
    assert np.array_equal(
        game_state_1.public_data.public_sheriff_checks.serialize(),
        game_state_2.public_data.public_sheriff_checks.serialize(),
    )
    assert np.array_equal(
        game_state_1.public_data.kills.serialize(),
        game_state_2.public_data.kills.serialize(),
    )

    assert np.array_equal(
        game_state_1.private_data.other_mafias.other_mafias,
        game_state_2.private_data.other_mafias.other_mafias,
    )

# Tests for voting rules with tie-breaking
def test_resolve_votes_no_tie():
    # Create a game state with 10 players
    game = CompleteGameState.build()
    
    # Set up votes: player 1 gets 3 votes, player 2 gets 2 votes
    for i in range(3):
        game.game_states[i].public_data.votes.checks[game.turn].checks[1] = 1
    
    for i in range(3, 5):
        game.game_states[i].public_data.votes.checks[game.turn].checks[2] = 1
    
    # Resolve votes
    game.resolve_votes()
    
    # Player 1 should be eliminated
    assert game.game_states[1].alive == 0
    assert game.game_states[2].alive == 1  # Player 2 should still be alive

def test_resolve_votes_with_tie_first_round():
    # Create a game state with 10 players
    game = CompleteGameState.build()
    
    # Set up votes: player 1 and player 2 both get 2 votes
    for i in range(2):
        game.game_states[i].public_data.votes.checks[game.turn].checks[1] = 1
    
    for i in range(2, 4):
        game.game_states[i].public_data.votes.checks[game.turn].checks[2] = 1
    
    # Resolve votes - this should trigger a second round of voting
    game.resolve_votes()
    
    # Both players should be in the tied_players list for second round voting
    assert 1 in game.tied_players
    assert 2 in game.tied_players
    assert game.voting_round == 1  # Should be in second round
    
    # Both players should still be alive after first round
    assert game.game_states[1].alive == 1
    assert game.game_states[2].alive == 1

def test_resolve_votes_second_round_no_tie():
    # Create a game state with 10 players and set up a tie from first round
    game = CompleteGameState.build()
    game.tied_players = [1, 2]
    game.voting_round = 1
    
    # Set up second round votes: player 1 gets 3 votes, player 2 gets 2 votes
    for i in range(3):
        game.game_states[i].public_data.votes.checks[game.turn].checks[1] = 1
    
    for i in range(3, 5):
        game.game_states[i].public_data.votes.checks[game.turn].checks[2] = 1
    
    # Resolve votes for second round
    game.resolve_votes()
    
    # Player 1 should be eliminated
    assert game.game_states[1].alive == 0
    assert game.game_states[2].alive == 1  # Player 2 should still be alive
    assert game.voting_round == 0  # Should reset to first round
    assert len(game.tied_players) == 0  # Tied players list should be cleared

def test_resolve_votes_second_round_with_tie():
    # Create a game state with 10 players and set up a tie from first round
    game = CompleteGameState.build()
    game.tied_players = [1, 2]
    game.voting_round = 1
    
    # Set up second round votes: player 1 and player 2 both get 2 votes
    for i in range(2):
        game.game_states[i].public_data.votes.checks[game.turn].checks[1] = 1
    
    for i in range(2, 4):
        game.game_states[i].public_data.votes.checks[game.turn].checks[2] = 1
    
    # Resolve votes for second round - this should trigger a third round
    game.resolve_votes()
    
    # Both players should still be in the tied_players list
    assert 1 in game.tied_players
    assert 2 in game.tied_players
    assert game.voting_round == 2  # Should be in third round
    
    # Both players should still be alive after second round
    assert game.game_states[1].alive == 1
    assert game.game_states[2].alive == 1

def test_resolve_votes_third_round():
    # Create a game state with 10 players and set up a tie from second round
    game = CompleteGameState.build()
    game.tied_players = [1, 2]
    game.voting_round = 2
    
    # Set up third round votes (doesn't matter what the votes are)
    for i in range(2):
        game.game_states[i].public_data.votes.checks[game.turn].checks[1] = 1
    
    for i in range(2, 4):
        game.game_states[i].public_data.votes.checks[game.turn].checks[2] = 1
    
    # Resolve votes for third round
    game.resolve_votes()
    
    # Both tied players should be eliminated
    assert game.game_states[1].alive == 0
    assert game.game_states[2].alive == 0
    assert game.voting_round == 0  # Should reset to first round
    assert len(game.tied_players) == 0  # Tied players list should be cleared

def test_resolve_votes_no_votes():
    # Create a game state with 10 players
    game = CompleteGameState.build()
    
    # No votes cast
    
    # Resolve votes
    game.resolve_votes()
    
    # No one should be eliminated
    for i in range(10):
        assert game.game_states[i].alive == 1
