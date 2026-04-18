import pytest
import requests

class TestIteration6GuestPlayersLineup:
    """Test PUT /api/matches/{id}/lineup with guest players (iteration 6)"""

    def test_lineup_accepts_mixed_user_ids_and_guest_objects(self, base_url, api_client, admin_client, test_run_id):
        """PUT /api/matches/{id}/lineup accepts mixed entries: user_ids AND guest objects {name, shirt_number}"""
        # Create match
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Mixed Lineup Match",
            "date": "2026-06-01T18:00:00Z",
            "team_size": 5
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Create 3 registered users
        registered_users = []
        for i in range(3):
            reg_response = api_client.post(f"{base_url}/api/auth/register", json={
                "email": f"TEST_mixed_player{i}_{test_run_id}@clubdodo.com",
                "password": "testpass123",
                "name": f"Registered Player {i}",
                "shirt_number": 10 + i
            })
            assert reg_response.status_code == 200
            user_id = reg_response.json()["user"]["id"]
            registered_users.append(user_id)
        
        # Override lineup with mix of registered users and guests
        lineup_response = admin_client.put(f"{base_url}/api/matches/{match_id}/lineup", json={
            "team_a": [
                registered_users[0],
                {"name": "Guest Alice", "shirt_number": 20},
                {"name": "Guest Bob", "shirt_number": 21}
            ],
            "team_b": [
                registered_users[1],
                {"name": "Guest Charlie", "shirt_number": 30},
                registered_users[2]
            ],
            "team_c": [],
            "reserves": [
                {"name": "Guest Reserve", "shirt_number": 99}
            ]
        })
        assert lineup_response.status_code == 200, f"Expected 200, got {lineup_response.status_code}: {lineup_response.text}"
        
        match = lineup_response.json()
        lineup = match["lineup"]
        
        # Verify team_a has 3 players (1 registered + 2 guests)
        assert len(lineup["team_a"]) == 3
        # Verify team_b has 3 players (2 registered + 1 guest)
        assert len(lineup["team_b"]) == 3
        # Verify reserves has 1 guest
        assert len(lineup["reserves"]) == 1

    def test_guests_get_synthetic_ids_with_guest_prefix(self, base_url, admin_client):
        """Guests get synthetic user_ids prefixed with 'guest:'"""
        # Create match
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Guest ID Match",
            "date": "2026-06-02T18:00:00Z",
            "team_size": 5
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Override lineup with guests only
        lineup_response = admin_client.put(f"{base_url}/api/matches/{match_id}/lineup", json={
            "team_a": [
                {"name": "Guest Player 1", "shirt_number": 7},
                {"name": "Guest Player 2", "shirt_number": 9}
            ],
            "team_b": [],
            "team_c": [],
            "reserves": []
        })
        assert lineup_response.status_code == 200
        
        lineup = lineup_response.json()["lineup"]
        
        # Verify all players in team_a have user_ids starting with 'guest:'
        for player in lineup["team_a"]:
            assert player["user_id"].startswith("guest:"), f"Expected guest: prefix, got {player['user_id']}"
            # Verify the rest of the ID looks like a UUID
            guest_id = player["user_id"][6:]  # Remove 'guest:' prefix
            assert len(guest_id) == 36, f"Expected UUID format after guest: prefix, got {guest_id}"

    def test_guests_have_is_guest_true_vote_guest_rating_zero(self, base_url, admin_client):
        """Guests have is_guest=true, vote='guest', rating=0"""
        # Create match
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Guest Attributes Match",
            "date": "2026-06-03T18:00:00Z",
            "team_size": 5
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Override lineup with guest
        lineup_response = admin_client.put(f"{base_url}/api/matches/{match_id}/lineup", json={
            "team_a": [
                {"name": "Guest Tester", "shirt_number": 42}
            ],
            "team_b": [],
            "team_c": [],
            "reserves": []
        })
        assert lineup_response.status_code == 200
        
        lineup = lineup_response.json()["lineup"]
        guest_player = lineup["team_a"][0]
        
        # Verify guest attributes
        assert guest_player["is_guest"] is True, f"Expected is_guest=true, got {guest_player.get('is_guest')}"
        assert guest_player["vote"] == "guest", f"Expected vote='guest', got {guest_player['vote']}"
        assert guest_player["rating"] == 0, f"Expected rating=0, got {guest_player['rating']}"
        assert guest_player["name"] == "Guest Tester"
        assert guest_player["shirt_number"] == 42
        assert guest_player["profile_picture"] is None
        assert guest_player["preferred_position"] is None

    def test_registered_user_without_vote_hydrated_correctly(self, base_url, api_client, admin_client, test_run_id):
        """Registered user who didn't vote is hydrated from users collection with vote defaulting to 'yes'"""
        # Create match
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Non-Voter Match",
            "date": "2026-06-04T18:00:00Z",
            "team_size": 5
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Create a registered user who does NOT vote on the match
        reg_response = api_client.post(f"{base_url}/api/auth/register", json={
            "email": f"TEST_non_voter_{test_run_id}@clubdodo.com",
            "password": "testpass123",
            "name": "Non Voter Player",
            "shirt_number": 15,
            "preferred_position": "MID"
        })
        assert reg_response.status_code == 200
        user_id = reg_response.json()["user"]["id"]
        
        # Override lineup with this user (who didn't vote)
        lineup_response = admin_client.put(f"{base_url}/api/matches/{match_id}/lineup", json={
            "team_a": [user_id],
            "team_b": [],
            "team_c": [],
            "reserves": []
        })
        assert lineup_response.status_code == 200
        
        lineup = lineup_response.json()["lineup"]
        player = lineup["team_a"][0]
        
        # Verify player is hydrated with correct details
        assert player["user_id"] == user_id
        assert player["name"] == "Non Voter Player"
        assert player["shirt_number"] == 15
        assert player["preferred_position"] == "MID"
        assert player["vote"] == "yes", f"Expected vote='yes' for non-voter, got {player['vote']}"
        assert "is_guest" not in player or player.get("is_guest") is not True

    def test_registered_user_with_vote_preserves_original_vote(self, base_url, api_client, admin_client, test_run_id):
        """Registered user who voted has their original vote preserved in lineup"""
        # Create match
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Voter Match",
            "date": "2026-06-05T18:00:00Z",
            "team_size": 5
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Create a registered user and vote 'reserve'
        reg_response = api_client.post(f"{base_url}/api/auth/register", json={
            "email": f"TEST_voter_iter6_{test_run_id}@clubdodo.com",
            "password": "testpass123",
            "name": "Voter Player"
        })
        assert reg_response.status_code == 200
        user_data = reg_response.json()
        user_id = user_data["user"]["id"]
        token = user_data["token"]
        
        # Vote 'reserve' on the match
        vote_response = api_client.post(
            f"{base_url}/api/matches/{match_id}/vote",
            headers={"Authorization": f"Bearer {token}"},
            json={"vote": "reserve"}
        )
        assert vote_response.status_code == 200
        
        # Override lineup with this user
        lineup_response = admin_client.put(f"{base_url}/api/matches/{match_id}/lineup", json={
            "team_a": [user_id],
            "team_b": [],
            "team_c": [],
            "reserves": []
        })
        assert lineup_response.status_code == 200
        
        lineup = lineup_response.json()["lineup"]
        player = lineup["team_a"][0]
        
        # Verify original vote is preserved
        assert player["vote"] == "reserve", f"Expected vote='reserve', got {player['vote']}"


class TestIteration6GuestPlayersMatchResult:
    """Test POST /api/matches/{id}/result with guest players (iteration 6)"""

    def test_match_result_with_guests_only_updates_real_user_stats(self, base_url, api_client, admin_client, test_run_id):
        """POST /api/matches/{id}/result with guests: only real users get goals/assists/matches_played incremented"""
        # Create match
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Result with Guests Match",
            "date": "2026-06-06T18:00:00Z",
            "team_size": 5
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Create 2 registered users
        users = []
        for i in range(2):
            reg_response = api_client.post(f"{base_url}/api/auth/register", json={
                "email": f"TEST_result_user{i}_{test_run_id}@clubdodo.com",
                "password": "testpass123",
                "name": f"Result User {i}",
                "shirt_number": 10 + i
            })
            assert reg_response.status_code == 200
            user_id = reg_response.json()["user"]["id"]
            users.append(user_id)
        
        # Get initial stats for users
        me_response_0 = api_client.get(f"{base_url}/api/auth/me", headers={"Authorization": f"Bearer {admin_client.headers['Authorization'].split()[1]}"})
        initial_stats_0 = api_client.get(f"{base_url}/api/users").json()
        user_0_initial = next(u for u in initial_stats_0 if u["id"] == users[0])
        user_1_initial = next(u for u in initial_stats_0 if u["id"] == users[1])
        
        # Override lineup with mix of users and guests
        lineup_response = admin_client.put(f"{base_url}/api/matches/{match_id}/lineup", json={
            "team_a": [
                users[0],
                {"name": "Guest Striker", "shirt_number": 9}
            ],
            "team_b": [
                users[1],
                {"name": "Guest Defender", "shirt_number": 5}
            ],
            "team_c": [],
            "reserves": []
        })
        assert lineup_response.status_code == 200
        
        lineup = lineup_response.json()["lineup"]
        guest_0_id = lineup["team_a"][1]["user_id"]
        guest_1_id = lineup["team_b"][1]["user_id"]
        
        # Record result with stats for both real users and guests
        result_response = admin_client.post(f"{base_url}/api/matches/{match_id}/result", json={
            "team_a_score": 3,
            "team_b_score": 2,
            "stats": [
                {"user_id": users[0], "goals": 2, "assists": 1},
                {"user_id": guest_0_id, "goals": 1, "assists": 0},  # Guest stats
                {"user_id": users[1], "goals": 1, "assists": 1},
                {"user_id": guest_1_id, "goals": 1, "assists": 1}   # Guest stats
            ]
        })
        assert result_response.status_code == 200, f"Expected 200, got {result_response.status_code}: {result_response.text}"
        
        # Get updated stats
        updated_stats = admin_client.get(f"{base_url}/api/users").json()
        user_0_updated = next(u for u in updated_stats if u["id"] == users[0])
        user_1_updated = next(u for u in updated_stats if u["id"] == users[1])
        
        # Verify real users' stats were updated
        assert user_0_updated["goals"] == user_0_initial["goals"] + 2, "User 0 goals should increase by 2"
        assert user_0_updated["assists"] == user_0_initial["assists"] + 1, "User 0 assists should increase by 1"
        assert user_0_updated["matches_played"] == user_0_initial["matches_played"] + 1, "User 0 matches_played should increase by 1"
        
        assert user_1_updated["goals"] == user_1_initial["goals"] + 1, "User 1 goals should increase by 1"
        assert user_1_updated["assists"] == user_1_initial["assists"] + 1, "User 1 assists should increase by 1"
        assert user_1_updated["matches_played"] == user_1_initial["matches_played"] + 1, "User 1 matches_played should increase by 1"
        
        # Verify no error occurred (guests were safely ignored)
        # If guests caused DB errors, the request would have failed with 500

    def test_editing_match_result_with_guests_reverts_real_users_only(self, base_url, api_client, admin_client, test_run_id):
        """Editing match result with guests: only real users' stats are reverted and re-applied"""
        # Create match
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Edit Result with Guests Match",
            "date": "2026-06-07T18:00:00Z",
            "team_size": 5
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Create 1 registered user
        reg_response = api_client.post(f"{base_url}/api/auth/register", json={
            "email": f"TEST_edit_result_user_{test_run_id}@clubdodo.com",
            "password": "testpass123",
            "name": "Edit Result User"
        })
        assert reg_response.status_code == 200
        user_id = reg_response.json()["user"]["id"]
        
        # Get initial stats
        initial_stats = admin_client.get(f"{base_url}/api/users").json()
        user_initial = next(u for u in initial_stats if u["id"] == user_id)
        
        # Override lineup with user and guest
        lineup_response = admin_client.put(f"{base_url}/api/matches/{match_id}/lineup", json={
            "team_a": [user_id],
            "team_b": [{"name": "Guest Opponent", "shirt_number": 10}],
            "team_c": [],
            "reserves": []
        })
        assert lineup_response.status_code == 200
        
        lineup = lineup_response.json()["lineup"]
        guest_id = lineup["team_b"][0]["user_id"]
        
        # Record initial result
        result_response_1 = admin_client.post(f"{base_url}/api/matches/{match_id}/result", json={
            "team_a_score": 2,
            "team_b_score": 1,
            "stats": [
                {"user_id": user_id, "goals": 2, "assists": 0},
                {"user_id": guest_id, "goals": 1, "assists": 0}
            ]
        })
        assert result_response_1.status_code == 200
        
        # Get stats after first result
        stats_after_first = admin_client.get(f"{base_url}/api/users").json()
        user_after_first = next(u for u in stats_after_first if u["id"] == user_id)
        assert user_after_first["goals"] == user_initial["goals"] + 2
        assert user_after_first["matches_played"] == user_initial["matches_played"] + 1
        
        # Edit result (change user's goals from 2 to 3)
        result_response_2 = admin_client.post(f"{base_url}/api/matches/{match_id}/result", json={
            "team_a_score": 3,
            "team_b_score": 1,
            "stats": [
                {"user_id": user_id, "goals": 3, "assists": 1},
                {"user_id": guest_id, "goals": 1, "assists": 0}
            ]
        })
        assert result_response_2.status_code == 200, f"Expected 200, got {result_response_2.status_code}: {result_response_2.text}"
        
        # Get stats after edit
        stats_after_edit = admin_client.get(f"{base_url}/api/users").json()
        user_after_edit = next(u for u in stats_after_edit if u["id"] == user_id)
        
        # Verify stats reflect the edited result (not cumulative)
        assert user_after_edit["goals"] == user_initial["goals"] + 3, "Goals should be initial + 3 (not +2+3)"
        assert user_after_edit["assists"] == user_initial["assists"] + 1, "Assists should be initial + 1"
        assert user_after_edit["matches_played"] == user_initial["matches_played"] + 1, "matches_played should still be +1"

    def test_delete_match_with_guests_reverts_real_users_stats(self, base_url, api_client, admin_client, test_run_id):
        """DELETE /api/matches/{id} with guests: only real users' stats are reverted"""
        # Create match
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Delete with Guests Match",
            "date": "2026-06-08T18:00:00Z",
            "team_size": 5
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Create 1 registered user
        reg_response = api_client.post(f"{base_url}/api/auth/register", json={
            "email": f"TEST_delete_user_{test_run_id}@clubdodo.com",
            "password": "testpass123",
            "name": "Delete User"
        })
        assert reg_response.status_code == 200
        user_id = reg_response.json()["user"]["id"]
        
        # Get initial stats
        initial_stats = admin_client.get(f"{base_url}/api/users").json()
        user_initial = next(u for u in initial_stats if u["id"] == user_id)
        
        # Override lineup with user and guest
        lineup_response = admin_client.put(f"{base_url}/api/matches/{match_id}/lineup", json={
            "team_a": [user_id],
            "team_b": [{"name": "Guest Delete Test", "shirt_number": 99}],
            "team_c": [],
            "reserves": []
        })
        assert lineup_response.status_code == 200
        
        lineup = lineup_response.json()["lineup"]
        guest_id = lineup["team_b"][0]["user_id"]
        
        # Record result
        result_response = admin_client.post(f"{base_url}/api/matches/{match_id}/result", json={
            "team_a_score": 5,
            "team_b_score": 0,
            "stats": [
                {"user_id": user_id, "goals": 5, "assists": 0},
                {"user_id": guest_id, "goals": 0, "assists": 0}
            ]
        })
        assert result_response.status_code == 200
        
        # Verify stats increased
        stats_after_result = admin_client.get(f"{base_url}/api/users").json()
        user_after_result = next(u for u in stats_after_result if u["id"] == user_id)
        assert user_after_result["goals"] == user_initial["goals"] + 5
        assert user_after_result["matches_played"] == user_initial["matches_played"] + 1
        
        # Delete match
        delete_response = admin_client.delete(f"{base_url}/api/matches/{match_id}")
        assert delete_response.status_code == 200, f"Expected 200, got {delete_response.status_code}: {delete_response.text}"
        assert delete_response.json()["ok"] is True
        
        # Verify stats reverted to initial
        stats_after_delete = admin_client.get(f"{base_url}/api/users").json()
        user_after_delete = next(u for u in stats_after_delete if u["id"] == user_id)
        assert user_after_delete["goals"] == user_initial["goals"], "Goals should be reverted to initial"
        assert user_after_delete["matches_played"] == user_initial["matches_played"], "matches_played should be reverted to initial"


class TestIteration6GuestPlayersLeague:
    """Test league match results with guest players (iteration 6)"""

    def test_league_match_with_guests_awards_points_to_real_users_only(self, base_url, api_client, admin_client, test_run_id):
        """League match result with guests: only registered users in winning team get league points"""
        # Create league match
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST League with Guests Match",
            "date": "2026-06-09T18:00:00Z",
            "team_size": 5,
            "match_type": "league"
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Create 2 registered users
        users = []
        for i in range(2):
            reg_response = api_client.post(f"{base_url}/api/auth/register", json={
                "email": f"TEST_league_guest_user{i}_{test_run_id}@clubdodo.com",
                "password": "testpass123",
                "name": f"League Guest User {i}"
            })
            assert reg_response.status_code == 200
            user_id = reg_response.json()["user"]["id"]
            users.append(user_id)
        
        # Get initial league points
        initial_stats = admin_client.get(f"{base_url}/api/users").json()
        user_0_initial = next(u for u in initial_stats if u["id"] == users[0])
        user_1_initial = next(u for u in initial_stats if u["id"] == users[1])
        
        # Override lineup with users and guests
        lineup_response = admin_client.put(f"{base_url}/api/matches/{match_id}/lineup", json={
            "team_a": [
                users[0],
                {"name": "Guest Winner", "shirt_number": 7}
            ],
            "team_b": [
                users[1],
                {"name": "Guest Loser", "shirt_number": 8}
            ],
            "team_c": [],
            "reserves": []
        })
        assert lineup_response.status_code == 200
        
        # Record result: team_a wins 3-1
        result_response = admin_client.post(f"{base_url}/api/matches/{match_id}/result", json={
            "team_a_score": 3,
            "team_b_score": 1,
            "stats": []
        })
        assert result_response.status_code == 200, f"Expected 200, got {result_response.status_code}: {result_response.text}"
        
        # Get updated league points
        updated_stats = admin_client.get(f"{base_url}/api/users").json()
        user_0_updated = next(u for u in updated_stats if u["id"] == users[0])
        user_1_updated = next(u for u in updated_stats if u["id"] == users[1])
        
        # Verify only real users got league points (3 for win, 0 for loss)
        assert user_0_updated["league_points"] == user_0_initial["league_points"] + 3, "Winner should get 3 league points"
        assert user_0_updated["wins"] == user_0_initial["wins"] + 1, "Winner should get 1 win"
        assert user_1_updated["league_points"] == user_1_initial["league_points"] + 0, "Loser should get 0 league points"
        assert user_1_updated["losses"] == user_1_initial["losses"] + 1, "Loser should get 1 loss"


class TestIteration6GuestPlayersValidation:
    """Test validation rules for guest players (iteration 6)"""

    def test_duplicate_registered_users_rejected_guests_allowed(self, base_url, api_client, admin_client, test_run_id):
        """Duplicate registered user_ids rejected (400), but multiple guests with same name allowed"""
        # Create match
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Duplicate Validation Match",
            "date": "2026-06-10T18:00:00Z",
            "team_size": 5
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Create 1 registered user
        reg_response = api_client.post(f"{base_url}/api/auth/register", json={
            "email": f"TEST_dup_user_{test_run_id}@clubdodo.com",
            "password": "testpass123",
            "name": "Dup User"
        })
        assert reg_response.status_code == 200
        user_id = reg_response.json()["user"]["id"]
        
        # Try to put same registered user in both teams (should fail)
        lineup_response_fail = admin_client.put(f"{base_url}/api/matches/{match_id}/lineup", json={
            "team_a": [user_id],
            "team_b": [user_id],
            "team_c": [],
            "reserves": []
        })
        assert lineup_response_fail.status_code == 400, f"Expected 400 for duplicate user, got {lineup_response_fail.status_code}"
        assert "multiple teams" in lineup_response_fail.text.lower()
        
        # Now try with multiple guests with same name (should succeed)
        lineup_response_success = admin_client.put(f"{base_url}/api/matches/{match_id}/lineup", json={
            "team_a": [
                {"name": "John Smith", "shirt_number": 10},
                {"name": "John Smith", "shirt_number": 11}
            ],
            "team_b": [
                {"name": "John Smith", "shirt_number": 12}
            ],
            "team_c": [],
            "reserves": []
        })
        assert lineup_response_success.status_code == 200, f"Expected 200 for multiple guests with same name, got {lineup_response_success.status_code}: {lineup_response_success.text}"
        
        lineup = lineup_response_success.json()["lineup"]
        # Verify all 3 "John Smith" guests have unique synthetic IDs
        guest_ids = [p["user_id"] for p in lineup["team_a"]] + [p["user_id"] for p in lineup["team_b"]]
        assert len(guest_ids) == 3
        assert len(set(guest_ids)) == 3, "All guest IDs should be unique even with same name"
        for gid in guest_ids:
            assert gid.startswith("guest:")

    def test_team_size_caps_enforced_with_mixed_entries(self, base_url, api_client, admin_client, test_run_id):
        """Team size caps enforced when mixing registered users and guests"""
        # Create match with team_size=3
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Team Size Mixed Match",
            "date": "2026-06-11T18:00:00Z",
            "team_size": 3
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Create 2 registered users
        users = []
        for i in range(2):
            reg_response = api_client.post(f"{base_url}/api/auth/register", json={
                "email": f"TEST_size_user{i}_{test_run_id}@clubdodo.com",
                "password": "testpass123",
                "name": f"Size User {i}"
            })
            assert reg_response.status_code == 200
            user_id = reg_response.json()["user"]["id"]
            users.append(user_id)
        
        # Try to exceed team_size with mix of users and guests (2 users + 2 guests = 4 > 3)
        lineup_response = admin_client.put(f"{base_url}/api/matches/{match_id}/lineup", json={
            "team_a": [
                users[0],
                users[1],
                {"name": "Guest 1", "shirt_number": 1},
                {"name": "Guest 2", "shirt_number": 2}
            ],
            "team_b": [],
            "team_c": [],
            "reserves": []
        })
        assert lineup_response.status_code == 400, f"Expected 400 for exceeding team_size, got {lineup_response.status_code}"
        assert "exceeds team size" in lineup_response.text.lower()
        
        # Now try with exactly team_size (2 users + 1 guest = 3)
        lineup_response_ok = admin_client.put(f"{base_url}/api/matches/{match_id}/lineup", json={
            "team_a": [
                users[0],
                users[1],
                {"name": "Guest 1", "shirt_number": 1}
            ],
            "team_b": [],
            "team_c": [],
            "reserves": []
        })
        assert lineup_response_ok.status_code == 200, f"Expected 200, got {lineup_response_ok.status_code}: {lineup_response_ok.text}"

    def test_guest_name_validation(self, base_url, admin_client):
        """Guest name must be 1-40 characters"""
        # Create match
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Guest Name Validation Match",
            "date": "2026-06-12T18:00:00Z",
            "team_size": 5
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Try with empty name (should fail)
        lineup_response_empty = admin_client.put(f"{base_url}/api/matches/{match_id}/lineup", json={
            "team_a": [{"name": "", "shirt_number": 1}],
            "team_b": [],
            "team_c": [],
            "reserves": []
        })
        assert lineup_response_empty.status_code == 422, f"Expected 422 for empty name, got {lineup_response_empty.status_code}"
        
        # Try with name > 40 characters (should fail)
        long_name = "A" * 41
        lineup_response_long = admin_client.put(f"{base_url}/api/matches/{match_id}/lineup", json={
            "team_a": [{"name": long_name, "shirt_number": 1}],
            "team_b": [],
            "team_c": [],
            "reserves": []
        })
        assert lineup_response_long.status_code == 422, f"Expected 422 for name > 40 chars, got {lineup_response_long.status_code}"
        
        # Try with valid name (should succeed)
        lineup_response_ok = admin_client.put(f"{base_url}/api/matches/{match_id}/lineup", json={
            "team_a": [{"name": "Valid Guest Name", "shirt_number": 1}],
            "team_b": [],
            "team_c": [],
            "reserves": []
        })
        assert lineup_response_ok.status_code == 200, f"Expected 200, got {lineup_response_ok.status_code}: {lineup_response_ok.text}"

    def test_guest_shirt_number_validation(self, base_url, admin_client):
        """Guest shirt_number must be 1-99 or null"""
        # Create match
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Guest Shirt Number Validation Match",
            "date": "2026-06-13T18:00:00Z",
            "team_size": 5
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Try with shirt_number = 0 (should fail)
        lineup_response_zero = admin_client.put(f"{base_url}/api/matches/{match_id}/lineup", json={
            "team_a": [{"name": "Guest Zero", "shirt_number": 0}],
            "team_b": [],
            "team_c": [],
            "reserves": []
        })
        assert lineup_response_zero.status_code == 422, f"Expected 422 for shirt_number=0, got {lineup_response_zero.status_code}"
        
        # Try with shirt_number = 100 (should fail)
        lineup_response_high = admin_client.put(f"{base_url}/api/matches/{match_id}/lineup", json={
            "team_a": [{"name": "Guest High", "shirt_number": 100}],
            "team_b": [],
            "team_c": [],
            "reserves": []
        })
        assert lineup_response_high.status_code == 422, f"Expected 422 for shirt_number=100, got {lineup_response_high.status_code}"
        
        # Try with shirt_number = null (should succeed)
        lineup_response_null = admin_client.put(f"{base_url}/api/matches/{match_id}/lineup", json={
            "team_a": [{"name": "Guest No Number"}],
            "team_b": [],
            "team_c": [],
            "reserves": []
        })
        assert lineup_response_null.status_code == 200, f"Expected 200 for null shirt_number, got {lineup_response_null.status_code}: {lineup_response_null.text}"
        
        # Verify shirt_number is null in response
        lineup = lineup_response_null.json()["lineup"]
        assert lineup["team_a"][0]["shirt_number"] is None
        
        # Try with valid shirt_number (should succeed)
        lineup_response_ok = admin_client.put(f"{base_url}/api/matches/{match_id}/lineup", json={
            "team_a": [{"name": "Guest Valid", "shirt_number": 42}],
            "team_b": [],
            "team_c": [],
            "reserves": []
        })
        assert lineup_response_ok.status_code == 200, f"Expected 200, got {lineup_response_ok.status_code}: {lineup_response_ok.text}"
