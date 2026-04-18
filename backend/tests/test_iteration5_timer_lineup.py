import pytest
import requests
from datetime import datetime, timezone

class TestIteration5DurationMinutes:
    """Test duration_minutes field in match creation (iteration 5)"""

    def test_post_matches_with_duration_minutes_persists_and_returns(self, base_url, admin_client):
        """POST /api/matches with duration_minutes in body (10-180 range) persists and returns it"""
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Duration 90min Match",
            "date": "2026-05-01T18:00:00Z",
            "team_size": 5,
            "duration_minutes": 90
        })
        assert match_response.status_code == 200, f"Expected 200, got {match_response.status_code}: {match_response.text}"
        
        match = match_response.json()
        assert match["duration_minutes"] == 90, f"Expected duration_minutes=90, got {match['duration_minutes']}"
        
        # Verify persistence via GET
        match_id = match["id"]
        get_response = admin_client.get(f"{base_url}/api/matches/{match_id}")
        assert get_response.status_code == 200
        fetched_match = get_response.json()
        assert fetched_match["duration_minutes"] == 90, f"Expected persisted duration_minutes=90, got {fetched_match['duration_minutes']}"

    def test_post_matches_duration_minutes_default_60_when_omitted(self, base_url, admin_client):
        """POST /api/matches defaults duration_minutes to 60 when omitted"""
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Default Duration Match",
            "date": "2026-05-02T18:00:00Z",
            "team_size": 5
        })
        assert match_response.status_code == 200, f"Expected 200, got {match_response.status_code}: {match_response.text}"
        
        match = match_response.json()
        assert match["duration_minutes"] == 60, f"Expected default duration_minutes=60, got {match['duration_minutes']}"

    def test_post_matches_duration_minutes_min_boundary_10(self, base_url, admin_client):
        """POST /api/matches accepts duration_minutes=10 (minimum boundary)"""
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Min Duration Match",
            "date": "2026-05-03T18:00:00Z",
            "team_size": 5,
            "duration_minutes": 10
        })
        assert match_response.status_code == 200, f"Expected 200, got {match_response.status_code}: {match_response.text}"
        
        match = match_response.json()
        assert match["duration_minutes"] == 10

    def test_post_matches_duration_minutes_max_boundary_180(self, base_url, admin_client):
        """POST /api/matches accepts duration_minutes=180 (maximum boundary)"""
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Max Duration Match",
            "date": "2026-05-04T18:00:00Z",
            "team_size": 5,
            "duration_minutes": 180
        })
        assert match_response.status_code == 200, f"Expected 200, got {match_response.status_code}: {match_response.text}"
        
        match = match_response.json()
        assert match["duration_minutes"] == 180

    def test_post_matches_duration_minutes_below_10_returns_422(self, base_url, admin_client):
        """POST /api/matches rejects duration_minutes < 10 with 422"""
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Invalid Duration Match",
            "date": "2026-05-05T18:00:00Z",
            "team_size": 5,
            "duration_minutes": 9
        })
        assert match_response.status_code == 422, f"Expected 422, got {match_response.status_code}: {match_response.text}"

    def test_post_matches_duration_minutes_above_180_returns_422(self, base_url, admin_client):
        """POST /api/matches rejects duration_minutes > 180 with 422"""
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Invalid Duration Match",
            "date": "2026-05-06T18:00:00Z",
            "team_size": 5,
            "duration_minutes": 181
        })
        assert match_response.status_code == 422, f"Expected 422, got {match_response.status_code}: {match_response.text}"


class TestIteration5TimerFields:
    """Test timer fields in match GET response (iteration 5)"""

    def test_get_match_returns_timer_fields_null_initially(self, base_url, admin_client):
        """GET /api/matches/{id} returns duration_minutes, timer_started_at (null initially), timer_ended_at (null initially)"""
        # Create match
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Timer Fields Match",
            "date": "2026-05-07T18:00:00Z",
            "team_size": 5,
            "duration_minutes": 45
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # GET match
        get_response = admin_client.get(f"{base_url}/api/matches/{match_id}")
        assert get_response.status_code == 200
        
        match = get_response.json()
        assert match["duration_minutes"] == 45
        assert match["timer_started_at"] is None, f"Expected timer_started_at=null, got {match['timer_started_at']}"
        assert match["timer_ended_at"] is None, f"Expected timer_ended_at=null, got {match['timer_ended_at']}"


class TestIteration5TimerStart:
    """Test POST /api/matches/{id}/timer/start endpoint (iteration 5)"""

    def test_timer_start_editor_sets_timer_started_at_and_clears_ended_at(self, base_url, admin_client):
        """POST /api/matches/{id}/timer/start (editor-only) sets timer_started_at=<now> and timer_ended_at=null"""
        # Create match
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Timer Start Match",
            "date": "2026-05-08T18:00:00Z",
            "team_size": 5
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Start timer
        before_start = datetime.now(timezone.utc)
        start_response = admin_client.post(f"{base_url}/api/matches/{match_id}/timer/start")
        after_start = datetime.now(timezone.utc)
        
        assert start_response.status_code == 200, f"Expected 200, got {start_response.status_code}: {start_response.text}"
        
        match = start_response.json()
        assert match["timer_started_at"] is not None, "Expected timer_started_at to be set"
        assert match["timer_ended_at"] is None, f"Expected timer_ended_at=null after start, got {match['timer_ended_at']}"
        
        # Verify timer_started_at is a valid ISO datetime string within reasonable time window
        started_at = datetime.fromisoformat(match["timer_started_at"].replace('Z', '+00:00'))
        assert before_start <= started_at <= after_start, "timer_started_at should be set to current time"
        
        # Verify persistence via GET
        get_response = admin_client.get(f"{base_url}/api/matches/{match_id}")
        assert get_response.status_code == 200
        fetched_match = get_response.json()
        assert fetched_match["timer_started_at"] == match["timer_started_at"]
        assert fetched_match["timer_ended_at"] is None

    def test_timer_start_non_editor_returns_403(self, base_url, api_client, test_run_id):
        """Non-editor user gets 403 on POST /api/matches/{id}/timer/start"""
        # Register regular user
        register_response = api_client.post(f"{base_url}/api/auth/register", json={
            "email": f"TEST_timer_non_editor_{test_run_id}@clubdodo.com",
            "password": "testpass123",
            "name": "Timer Non Editor"
        })
        assert register_response.status_code == 200
        token = register_response.json()["token"]
        
        # Create match
        match_response = api_client.post(
            f"{base_url}/api/matches",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "title": "TEST Timer Non-editor Match",
                "date": "2026-05-09T18:00:00Z",
                "team_size": 5
            }
        )
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Try to start timer
        start_response = api_client.post(
            f"{base_url}/api/matches/{match_id}/timer/start",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert start_response.status_code == 403, f"Expected 403, got {start_response.status_code}"


class TestIteration5TimerStop:
    """Test POST /api/matches/{id}/timer/stop endpoint (iteration 5)"""

    def test_timer_stop_editor_sets_timer_ended_at_preserves_started_at(self, base_url, admin_client):
        """POST /api/matches/{id}/timer/stop (editor-only) sets timer_ended_at=<now>, timer_started_at preserved"""
        # Create match
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Timer Stop Match",
            "date": "2026-05-10T18:00:00Z",
            "team_size": 5
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Start timer
        start_response = admin_client.post(f"{base_url}/api/matches/{match_id}/timer/start")
        assert start_response.status_code == 200
        started_at = start_response.json()["timer_started_at"]
        
        # Stop timer
        before_stop = datetime.now(timezone.utc)
        stop_response = admin_client.post(f"{base_url}/api/matches/{match_id}/timer/stop")
        after_stop = datetime.now(timezone.utc)
        
        assert stop_response.status_code == 200, f"Expected 200, got {stop_response.status_code}: {stop_response.text}"
        
        match = stop_response.json()
        assert match["timer_started_at"] == started_at, "timer_started_at should be preserved"
        assert match["timer_ended_at"] is not None, "Expected timer_ended_at to be set"
        
        # Verify timer_ended_at is a valid ISO datetime string within reasonable time window
        ended_at = datetime.fromisoformat(match["timer_ended_at"].replace('Z', '+00:00'))
        assert before_stop <= ended_at <= after_stop, "timer_ended_at should be set to current time"
        
        # Verify persistence via GET
        get_response = admin_client.get(f"{base_url}/api/matches/{match_id}")
        assert get_response.status_code == 200
        fetched_match = get_response.json()
        assert fetched_match["timer_started_at"] == started_at
        assert fetched_match["timer_ended_at"] == match["timer_ended_at"]

    def test_timer_stop_non_editor_returns_403(self, base_url, api_client, test_run_id):
        """Non-editor user gets 403 on POST /api/matches/{id}/timer/stop"""
        # Register regular user
        register_response = api_client.post(f"{base_url}/api/auth/register", json={
            "email": f"TEST_timer_stop_non_editor_{test_run_id}@clubdodo.com",
            "password": "testpass123",
            "name": "Timer Stop Non Editor"
        })
        assert register_response.status_code == 200
        token = register_response.json()["token"]
        
        # Create match
        match_response = api_client.post(
            f"{base_url}/api/matches",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "title": "TEST Timer Stop Non-editor Match",
                "date": "2026-05-11T18:00:00Z",
                "team_size": 5
            }
        )
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Try to stop timer
        stop_response = api_client.post(
            f"{base_url}/api/matches/{match_id}/timer/stop",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert stop_response.status_code == 403, f"Expected 403, got {stop_response.status_code}"


class TestIteration5TimerReset:
    """Test POST /api/matches/{id}/timer/reset endpoint (iteration 5)"""

    def test_timer_reset_editor_clears_both_timer_fields(self, base_url, admin_client):
        """POST /api/matches/{id}/timer/reset (editor-only) clears both timer_started_at and timer_ended_at"""
        # Create match
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Timer Reset Match",
            "date": "2026-05-12T18:00:00Z",
            "team_size": 5
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Start and stop timer
        admin_client.post(f"{base_url}/api/matches/{match_id}/timer/start")
        stop_response = admin_client.post(f"{base_url}/api/matches/{match_id}/timer/stop")
        assert stop_response.status_code == 200
        
        # Verify both fields are set
        match_after_stop = stop_response.json()
        assert match_after_stop["timer_started_at"] is not None
        assert match_after_stop["timer_ended_at"] is not None
        
        # Reset timer
        reset_response = admin_client.post(f"{base_url}/api/matches/{match_id}/timer/reset")
        assert reset_response.status_code == 200, f"Expected 200, got {reset_response.status_code}: {reset_response.text}"
        
        match = reset_response.json()
        assert match["timer_started_at"] is None, f"Expected timer_started_at=null after reset, got {match['timer_started_at']}"
        assert match["timer_ended_at"] is None, f"Expected timer_ended_at=null after reset, got {match['timer_ended_at']}"
        
        # Verify persistence via GET
        get_response = admin_client.get(f"{base_url}/api/matches/{match_id}")
        assert get_response.status_code == 200
        fetched_match = get_response.json()
        assert fetched_match["timer_started_at"] is None
        assert fetched_match["timer_ended_at"] is None

    def test_timer_reset_non_editor_returns_403(self, base_url, api_client, test_run_id):
        """Non-editor user gets 403 on POST /api/matches/{id}/timer/reset"""
        # Register regular user
        register_response = api_client.post(f"{base_url}/api/auth/register", json={
            "email": f"TEST_timer_reset_non_editor_{test_run_id}@clubdodo.com",
            "password": "testpass123",
            "name": "Timer Reset Non Editor"
        })
        assert register_response.status_code == 200
        token = register_response.json()["token"]
        
        # Create match
        match_response = api_client.post(
            f"{base_url}/api/matches",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "title": "TEST Timer Reset Non-editor Match",
                "date": "2026-05-13T18:00:00Z",
                "team_size": 5
            }
        )
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Try to reset timer
        reset_response = api_client.post(
            f"{base_url}/api/matches/{match_id}/timer/reset",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert reset_response.status_code == 403, f"Expected 403, got {reset_response.status_code}"


class TestIteration5LineupOverride:
    """Test PUT /api/matches/{id}/lineup endpoint for manual lineup override (iteration 5)"""

    def test_lineup_override_editor_accepts_team_arrays_and_rehydrates(self, base_url, api_client, admin_client, test_run_id):
        """PUT /api/matches/{id}/lineup (editor-only) accepts {team_a, team_b, team_c, reserves} as arrays of user_ids. Rehydrates with user details."""
        # Create match
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Lineup Override Match",
            "date": "2026-05-14T18:00:00Z",
            "team_size": 3
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Create 8 players
        players = []
        for i in range(8):
            reg_response = api_client.post(f"{base_url}/api/auth/register", json={
                "email": f"TEST_lineup_override_player{i}_{test_run_id}@clubdodo.com",
                "password": "testpass123",
                "name": f"Override Player {i}",
                "shirt_number": 20 + i
            })
            assert reg_response.status_code == 200
            user_id = reg_response.json()["user"]["id"]
            players.append(user_id)
        
        # Override lineup: team_a=[0,1,2], team_b=[3,4,5], team_c=[], reserves=[6,7]
        lineup_response = admin_client.put(f"{base_url}/api/matches/{match_id}/lineup", json={
            "team_a": [players[0], players[1], players[2]],
            "team_b": [players[3], players[4], players[5]],
            "team_c": [],
            "reserves": [players[6], players[7]]
        })
        assert lineup_response.status_code == 200, f"Expected 200, got {lineup_response.status_code}: {lineup_response.text}"
        
        match = lineup_response.json()
        assert match["lineup"] is not None
        
        lineup = match["lineup"]
        assert len(lineup["team_a"]) == 3
        assert len(lineup["team_b"]) == 3
        assert len(lineup["team_c"]) == 0
        assert len(lineup["reserves"]) == 2
        
        # Verify rehydration: each player should have user_id, name, shirt_number, rating, vote
        for i, player_obj in enumerate(lineup["team_a"]):
            assert player_obj["user_id"] == players[i]
            assert player_obj["name"] == f"Override Player {i}"
            assert player_obj["shirt_number"] == 20 + i
            assert "rating" in player_obj
            assert "vote" in player_obj
        
        # Verify persistence via GET
        get_response = admin_client.get(f"{base_url}/api/matches/{match_id}")
        assert get_response.status_code == 200
        fetched_match = get_response.json()
        assert len(fetched_match["lineup"]["team_a"]) == 3
        assert len(fetched_match["lineup"]["team_b"]) == 3

    def test_lineup_override_sets_status_scheduled_if_voting(self, base_url, admin_client):
        """PUT /api/matches/{id}/lineup sets status='scheduled' if it was 'voting'"""
        # Create match (status starts as 'voting')
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Lineup Override Status Match",
            "date": "2026-05-15T18:00:00Z",
            "team_size": 3
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        assert match_response.json()["status"] == "voting"
        
        # Override lineup with empty arrays
        lineup_response = admin_client.put(f"{base_url}/api/matches/{match_id}/lineup", json={
            "team_a": [],
            "team_b": [],
            "team_c": [],
            "reserves": []
        })
        assert lineup_response.status_code == 200
        
        match = lineup_response.json()
        assert match["status"] == "scheduled", f"Expected status='scheduled', got {match['status']}"

    def test_lineup_override_rejects_duplicate_user_in_multiple_teams(self, base_url, api_client, admin_client, test_run_id):
        """PUT /api/matches/{id}/lineup rejects duplicate user in multiple teams with 400"""
        # Create match
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Lineup Duplicate Match",
            "date": "2026-05-16T18:00:00Z",
            "team_size": 3
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Create 2 players
        players = []
        for i in range(2):
            reg_response = api_client.post(f"{base_url}/api/auth/register", json={
                "email": f"TEST_lineup_dup_player{i}_{test_run_id}@clubdodo.com",
                "password": "testpass123",
                "name": f"Dup Player {i}"
            })
            assert reg_response.status_code == 200
            user_id = reg_response.json()["user"]["id"]
            players.append(user_id)
        
        # Try to put same player in team_a and team_b
        lineup_response = admin_client.put(f"{base_url}/api/matches/{match_id}/lineup", json={
            "team_a": [players[0]],
            "team_b": [players[0], players[1]],
            "team_c": [],
            "reserves": []
        })
        assert lineup_response.status_code == 400, f"Expected 400, got {lineup_response.status_code}: {lineup_response.text}"
        assert "multiple teams" in lineup_response.text.lower(), "Error message should mention duplicate player"

    def test_lineup_override_rejects_team_a_exceeds_team_size(self, base_url, api_client, admin_client, test_run_id):
        """PUT /api/matches/{id}/lineup rejects when team_a exceeds team_size with 400"""
        # Create match with team_size=3
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Lineup Exceed Team A Match",
            "date": "2026-05-17T18:00:00Z",
            "team_size": 3
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Create 4 players
        players = []
        for i in range(4):
            reg_response = api_client.post(f"{base_url}/api/auth/register", json={
                "email": f"TEST_lineup_exceed_a_player{i}_{test_run_id}@clubdodo.com",
                "password": "testpass123",
                "name": f"Exceed A Player {i}"
            })
            assert reg_response.status_code == 200
            user_id = reg_response.json()["user"]["id"]
            players.append(user_id)
        
        # Try to put 4 players in team_a (exceeds team_size=3)
        lineup_response = admin_client.put(f"{base_url}/api/matches/{match_id}/lineup", json={
            "team_a": [players[0], players[1], players[2], players[3]],
            "team_b": [],
            "team_c": [],
            "reserves": []
        })
        assert lineup_response.status_code == 400, f"Expected 400, got {lineup_response.status_code}: {lineup_response.text}"
        assert "exceeds team size" in lineup_response.text.lower(), "Error message should mention team size exceeded"

    def test_lineup_override_rejects_team_b_exceeds_team_size(self, base_url, api_client, admin_client, test_run_id):
        """PUT /api/matches/{id}/lineup rejects when team_b exceeds team_size with 400"""
        # Create match with team_size=3
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Lineup Exceed Team B Match",
            "date": "2026-05-18T18:00:00Z",
            "team_size": 3
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Create 4 players
        players = []
        for i in range(4):
            reg_response = api_client.post(f"{base_url}/api/auth/register", json={
                "email": f"TEST_lineup_exceed_b_player{i}_{test_run_id}@clubdodo.com",
                "password": "testpass123",
                "name": f"Exceed B Player {i}"
            })
            assert reg_response.status_code == 200
            user_id = reg_response.json()["user"]["id"]
            players.append(user_id)
        
        # Try to put 4 players in team_b (exceeds team_size=3)
        lineup_response = admin_client.put(f"{base_url}/api/matches/{match_id}/lineup", json={
            "team_a": [],
            "team_b": [players[0], players[1], players[2], players[3]],
            "team_c": [],
            "reserves": []
        })
        assert lineup_response.status_code == 400, f"Expected 400, got {lineup_response.status_code}: {lineup_response.text}"
        assert "exceeds team size" in lineup_response.text.lower()

    def test_lineup_override_team_c_with_players_auto_sets_third_team_enabled(self, base_url, api_client, admin_client, test_run_id):
        """PUT /api/matches/{id}/lineup with team_c containing players auto-sets match.third_team_enabled=true"""
        # Create match with third_team_enabled=false
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Lineup Team C Auto Enable Match",
            "date": "2026-05-19T18:00:00Z",
            "team_size": 3,
            "third_team_enabled": False
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        assert match_response.json()["third_team_enabled"] is False
        
        # Create 9 players
        players = []
        for i in range(9):
            reg_response = api_client.post(f"{base_url}/api/auth/register", json={
                "email": f"TEST_lineup_team_c_player{i}_{test_run_id}@clubdodo.com",
                "password": "testpass123",
                "name": f"Team C Player {i}"
            })
            assert reg_response.status_code == 200
            user_id = reg_response.json()["user"]["id"]
            players.append(user_id)
        
        # Override lineup with team_c containing players
        lineup_response = admin_client.put(f"{base_url}/api/matches/{match_id}/lineup", json={
            "team_a": [players[0], players[1], players[2]],
            "team_b": [players[3], players[4], players[5]],
            "team_c": [players[6], players[7], players[8]],
            "reserves": []
        })
        assert lineup_response.status_code == 200, f"Expected 200, got {lineup_response.status_code}: {lineup_response.text}"
        
        match = lineup_response.json()
        assert match["third_team_enabled"] is True, f"Expected third_team_enabled=true, got {match['third_team_enabled']}"
        assert match["lineup"]["third_team_enabled"] is True
        
        # Verify persistence via GET
        get_response = admin_client.get(f"{base_url}/api/matches/{match_id}")
        assert get_response.status_code == 200
        fetched_match = get_response.json()
        assert fetched_match["third_team_enabled"] is True

    def test_lineup_override_with_empty_arrays_works(self, base_url, admin_client):
        """PUT /api/matches/{id}/lineup with empty arrays works (can reset lineup)"""
        # Create match
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Lineup Empty Arrays Match",
            "date": "2026-05-20T18:00:00Z",
            "team_size": 3
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Override lineup with empty arrays
        lineup_response = admin_client.put(f"{base_url}/api/matches/{match_id}/lineup", json={
            "team_a": [],
            "team_b": [],
            "team_c": [],
            "reserves": []
        })
        assert lineup_response.status_code == 200, f"Expected 200, got {lineup_response.status_code}: {lineup_response.text}"
        
        match = lineup_response.json()
        assert match["lineup"] is not None
        assert len(match["lineup"]["team_a"]) == 0
        assert len(match["lineup"]["team_b"]) == 0
        assert len(match["lineup"]["team_c"]) == 0
        assert len(match["lineup"]["reserves"]) == 0

    def test_lineup_override_non_editor_returns_403(self, base_url, api_client, test_run_id):
        """Non-editor user gets 403 on PUT /api/matches/{id}/lineup"""
        # Register regular user
        register_response = api_client.post(f"{base_url}/api/auth/register", json={
            "email": f"TEST_lineup_override_non_editor_{test_run_id}@clubdodo.com",
            "password": "testpass123",
            "name": "Lineup Override Non Editor"
        })
        assert register_response.status_code == 200
        token = register_response.json()["token"]
        
        # Create match
        match_response = api_client.post(
            f"{base_url}/api/matches",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "title": "TEST Lineup Override Non-editor Match",
                "date": "2026-05-21T18:00:00Z",
                "team_size": 5
            }
        )
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Try to override lineup
        lineup_response = api_client.put(
            f"{base_url}/api/matches/{match_id}/lineup",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "team_a": [],
                "team_b": [],
                "team_c": [],
                "reserves": []
            }
        )
        assert lineup_response.status_code == 403, f"Expected 403, got {lineup_response.status_code}"
