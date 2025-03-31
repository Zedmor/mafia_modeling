import pytest
import json
import numpy as np
from mafia_server.models import (
    Role, Team, Phase, Player, GameState,
    ActionRequest, ActionResponse, GameEvent
)

def test_role_enum():
    """Test Role enum values and properties"""
    assert Role.CITIZEN.team == Team.RED
    assert Role.SHERIFF.team == Team.RED
    assert Role.MAFIA.team == Team.BLACK
    assert Role.DON.team == Team.BLACK

def test_player_model():
    """Test Player model initialization and properties"""
    player = Player(player_id=0, role=Role.CITIZEN)
    assert player.player_id == 0
    assert player.role == Role.CITIZEN
    assert player.team == Team.RED
    assert player.alive
    
    # Test serialization
    serialized = player.to_dict()
    assert serialized["player_id"] == 0
    assert serialized["role"] == "CITIZEN"
    assert serialized["alive"]

def test_game_state_initialization():
    """Test GameState initialization with proper player count and roles"""
    game_state = GameState.new_game()
    assert len(game_state.players) == 10
    
    # Count roles
    role_counts = {
        Role.CITIZEN: 0,
        Role.SHERIFF: 0,
        Role.MAFIA: 0,
        Role.DON: 0
    }
    
    for player in game_state.players:
        role_counts[player.role] += 1
    
    assert role_counts[Role.CITIZEN] == 6
    assert role_counts[Role.SHERIFF] == 1
    assert role_counts[Role.MAFIA] == 2
    assert role_counts[Role.DON] == 1
    
    # Check initial phase
    assert game_state.current_phase == Phase.DECLARATION
    assert game_state.turn == 0
    assert game_state.active_player == 0

def test_action_request_serialization():
    """Test that ActionRequest objects can be properly serialized/deserialized"""
    request = ActionRequest(
        type="ACTION_REQUEST",
        player_id=0,
        phase=Phase.DECLARATION.name,
        valid_actions={
            "declaration": "vector_10",
            "sheriff_claims": "matrix_10x10",
            "nomination": [-1, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        },
        observation={
            "role": "CITIZEN",
            "alive_players": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
            "known_roles": {},
            "day": 0,
            "private_info": {}
        }
    )
    
    # Test JSON serialization
    json_str = json.dumps(request.to_dict())
    loaded = ActionRequest.from_dict(json.loads(json_str))
    
    assert loaded.player_id == 0
    assert loaded.phase == Phase.DECLARATION.name
    assert loaded.valid_actions["nomination"] == [-1, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    assert loaded.observation["role"] == "CITIZEN"

def test_action_response_serialization():
    """Test that ActionResponse objects can be properly serialized/deserialized"""
    response = ActionResponse(
        type="ACTION_RESPONSE",
        player_id=0,
        action={
            "type": "DECLARATION",
            "declaration": [0, 0, -2, 1, 0, 3, 0, 0, 0, 0],
            "sheriff_claims": [[0,0,0,1,0,0,0,0,0,0], [0,0,0,0,-1,0,0,0,0,0]],
            "nomination_policy": {
                "2": 0.3,
                "4": 0.4,
                "5": 0.3
            }
        }
    )
    
    # Test JSON serialization
    json_str = json.dumps(response.to_dict())
    loaded = ActionResponse.from_dict(json.loads(json_str))
    
    assert loaded.player_id == 0
    assert loaded.action["type"] == "DECLARATION"
    assert loaded.action["declaration"] == [0, 0, -2, 1, 0, 3, 0, 0, 0, 0]
    assert loaded.action["nomination_policy"]["2"] == 0.3
    
def test_game_event_serialization():
    """Test that GameEvent objects can be properly serialized/deserialized"""
    event = GameEvent(
        type="GAME_EVENT",
        event="PLAYER_ELIMINATED",
        player_id=3,
        revealed_role="CITIZEN",
        next_phase="NIGHT_KILL"
    )
    
    # Test JSON serialization
    json_str = json.dumps(event.to_dict())
    loaded = GameEvent.from_dict(json.loads(json_str))
    
    assert loaded.event == "PLAYER_ELIMINATED"
    assert loaded.player_id == 3
    assert loaded.revealed_role == "CITIZEN"
    assert loaded.next_phase == "NIGHT_KILL"
