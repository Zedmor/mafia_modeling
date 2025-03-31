import pytest
from mafia_server.models import (
    Role, Team, Phase, Player, GameState,
    ActionRequest, ActionResponse, GameEvent
)

@pytest.fixture
def game_state():
    """Fixture to create a standard game state for testing"""
    return GameState.new_game()

def test_sheriff_claims_validation(game_state):
    """Test validation of sheriff claims"""
    # Valid sheriff claims (10x10 matrix)
    valid_claims = [[0] * 10 for _ in range(10)]
    # First night: checked player 3, found RED
    valid_claims[0][3] = 1  
    # Second night: checked player 4, found BLACK
    valid_claims[1][4] = -1
    
    game_state.apply_declaration(0, [0] * 10, valid_claims)
    
    # Should be stored properly
    assert game_state.players[0].sheriff_claims == valid_claims
    
    # Test with not enough rows (should be 10x10)
    not_enough_rows = [
        [0, 0, 0, 1, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, -1, 0, 0, 0, 0, 0]
    ]
    
    with pytest.raises(ValueError, match="Sheriff claims must be a 10x10 matrix"):
        game_state.apply_declaration(0, [0] * 10, not_enough_rows)
    
    # Test with proper number of rows but invalid column length
    invalid_column_length = [[0] * 10 for _ in range(10)]
    invalid_column_length[3] = [0, 0, 0, 1, 0, 0, 0, 0, 0]  # Only 9 elements in row 3
    
    with pytest.raises(ValueError, match="Each sheriff claim vector must have length 10"):
        game_state.apply_declaration(0, [0] * 10, invalid_column_length)
    
    # Invalid values
    invalid_values = [[0] * 10 for _ in range(10)]
    invalid_values[2][3] = 2  # 2 is not valid (only -1, 0, 1 are allowed)
    
    with pytest.raises(ValueError, match="Sheriff claim values must be -1, 0, or 1"):
        game_state.apply_declaration(0, [0] * 10, invalid_values)
    
    # Not a list of lists
    not_list_of_lists = "not a list"
    with pytest.raises(ValueError, match="Sheriff claims must be a list of lists"):
        game_state.apply_declaration(0, [0] * 10, not_list_of_lists)

def test_sheriff_claims_in_observations(game_state):
    """Test that sheriff claims are properly included in observations"""
    # Create a 10x10 matrix
    sheriff_claims = [[0] * 10 for _ in range(10)]
    # Set claims for two turns
    sheriff_claims[0][3] = 1     # Turn 0: checked player 3, found RED
    sheriff_claims[1][4] = -1    # Turn 1: checked player 4, found BLACK
    
    # Apply declaration from player 0
    game_state.apply_declaration(0, [0] * 10, sheriff_claims)
    
    # Check observation for player 0
    observation = game_state.get_observation(0)
    assert observation["players"][0]["sheriff_claims"] == sheriff_claims
    
    # Check observation for player 1
    observation = game_state.get_observation(1)
    assert observation["players"][0]["sheriff_claims"] == sheriff_claims

def test_sequential_sheriff_claims(game_state):
    """Test sequential sheriff claims across multiple turns"""
    # Turn 1: Player 0 declares
    turn1_claims = [[0] * 10 for _ in range(10)]
    turn1_claims[0][3] = 1  # Checked player 3, found RED
    game_state.apply_declaration(0, [0] * 10, turn1_claims)
    
    # Turn 2: Player 0 declares again, adding a new claim
    turn2_claims = [[0] * 10 for _ in range(10)]
    turn2_claims[0][3] = 1  # Checked player 3, found RED
    turn2_claims[1][4] = -1  # Checked player 4, found BLACK
    game_state.apply_declaration(0, [0] * 10, turn2_claims)
    
    # Check that the claims were updated
    assert game_state.players[0].sheriff_claims == turn2_claims
    
    # Turn 3: Player 1 makes a claim
    player1_claims = [[0] * 10 for _ in range(10)]
    player1_claims[0][3] = -1  # Claims player 3 is BLACK (contradicting player 0)
    game_state.apply_declaration(1, [0] * 10, player1_claims)
    
    # Verify each player's claims
    assert game_state.players[0].sheriff_claims == turn2_claims
    assert game_state.players[1].sheriff_claims == player1_claims
    
    # Check observation from player 2's perspective
    observation = game_state.get_observation(2)
    assert observation["players"][0]["sheriff_claims"] == turn2_claims
    assert observation["players"][1]["sheriff_claims"] == player1_claims

def test_sheriff_claims_in_action_request():
    """Test that sheriff claims are properly included in action requests"""
    game = GameState.new_game()
    
    # Get valid actions for player 0 in declaration phase
    game.active_player = 0
    valid_actions = game.get_valid_actions()
    
    # Check if sheriff_claims is in valid actions
    assert "sheriff_claims" in valid_actions
    assert valid_actions["sheriff_claims"] == "matrix_10x10"
    
    # Create action request
    request = ActionRequest(
        type="ACTION_REQUEST",
        player_id=0,
        phase=game.current_phase.name,
        valid_actions=valid_actions,
        observation=game.get_observation(0)
    )
    
    # Check valid actions in action request
    request_dict = request.to_dict()
    assert "sheriff_claims" in request_dict["valid_actions"]
    assert request_dict["valid_actions"]["sheriff_claims"] == "matrix_10x10"
