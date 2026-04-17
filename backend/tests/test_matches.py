import pytest
import requests

class TestMatches:
    """Match CRUD, voting, lineup generation, and result recording tests"""

    def test_post_matches_creates_match_any_authenticated_user(self, base_url, api_client, test_run_id):
        """POST /api/matches creates match (any authenticated user)"""
        # Register a regular user
        register_response = api_client.post(f"{base_url}/api/auth/register", json={
            "email": f"TEST_match_creator_{test_run_id}@clubdodo.com",
            "password": "testpass123",
            "name": "Match Creator"
        })
        assert register_response.status_code == 200
        token = register_response.json()["token"]
        user_id = register_response.json()["user"]["id"]
        
        # Create match
        match_response = api_client.post(
            f"{base_url}/api/matches",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "title": "TEST Friday Night Game",
                "date": "2026-03-15T19:00:00Z",
                "location": "Central Park",
                "team_size": 5
            }
        )
        assert match_response.status_code == 200, f"Expected 200, got {match_response.status_code}: {match_response.text}"
        
        match = match_response.json()
        assert match["title"] == "TEST Friday Night Game"
        assert match["date"] == "2026-03-15T19:00:00Z"
        assert match["location"] == "Central Park"
        assert match["team_size"] == 5
        assert match["status"] == "voting"
        assert match["created_by"] == user_id
        assert "id" in match
        assert "created_at" in match
        assert match["votes"] == []
        assert match["lineup"] is None
        assert match["result"] is None
        assert "_id" not in match

    def test_get_matches_lists_matches(self, base_url, admin_client):
        """GET /api/matches lists matches"""
        response = admin_client.get(f"{base_url}/api/matches")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        matches = response.json()
        assert isinstance(matches, list)
        
        for match in matches:
            assert "id" in match
            assert "title" in match
            assert "date" in match
            assert "status" in match
            assert "votes" in match
            assert "_id" not in match

    def test_get_match_by_id_returns_match_with_votes_array(self, base_url, api_client, admin_client, test_run_id):
        """GET /api/matches/{id} returns match with votes array containing {user_id, name, shirt_number, rating, vote}"""
        # Create a match
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Vote Test Match",
            "date": "2026-03-20T18:00:00Z",
            "team_size": 5
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Register a user and vote
        register_response = api_client.post(f"{base_url}/api/auth/register", json={
            "email": f"TEST_voter_{test_run_id}@clubdodo.com",
            "password": "testpass123",
            "name": "Test Voter",
            "shirt_number": 7
        })
        assert register_response.status_code == 200
        token = register_response.json()["token"]
        user_id = register_response.json()["user"]["id"]
        
        # Vote on match
        vote_response = api_client.post(
            f"{base_url}/api/matches/{match_id}/vote",
            headers={"Authorization": f"Bearer {token}"},
            json={"vote": "yes"}
        )
        assert vote_response.status_code == 200
        
        # Get match details
        get_response = api_client.get(
            f"{base_url}/api/matches/{match_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert get_response.status_code == 200
        
        match = get_response.json()
        assert len(match["votes"]) >= 1
        
        # Find the voter in votes array
        voter = next((v for v in match["votes"] if v["user_id"] == user_id), None)
        assert voter is not None, "Voter should be in votes array"
        assert voter["name"] == "Test Voter"
        assert voter["shirt_number"] == 7
        assert voter["rating"] == 0.0
        assert voter["vote"] == "yes"
        assert "_id" not in match

    def test_post_match_vote_stores_and_overwrites_previous_vote(self, base_url, api_client, test_run_id):
        """POST /api/matches/{id}/vote stores vote (yes/no/reserve), overwrites previous vote for same user"""
        # Register user
        register_response = api_client.post(f"{base_url}/api/auth/register", json={
            "email": f"TEST_vote_changer_{test_run_id}@clubdodo.com",
            "password": "testpass123",
            "name": "Vote Changer"
        })
        assert register_response.status_code == 200
        token = register_response.json()["token"]
        user_id = register_response.json()["user"]["id"]
        
        # Create match
        match_response = api_client.post(
            f"{base_url}/api/matches",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "title": "TEST Vote Change Match",
                "date": "2026-03-25T19:00:00Z",
                "team_size": 5
            }
        )
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Vote "yes"
        vote1_response = api_client.post(
            f"{base_url}/api/matches/{match_id}/vote",
            headers={"Authorization": f"Bearer {token}"},
            json={"vote": "yes"}
        )
        assert vote1_response.status_code == 200
        match1 = vote1_response.json()
        voter1 = next((v for v in match1["votes"] if v["user_id"] == user_id), None)
        assert voter1["vote"] == "yes"
        
        # Change vote to "no"
        vote2_response = api_client.post(
            f"{base_url}/api/matches/{match_id}/vote",
            headers={"Authorization": f"Bearer {token}"},
            json={"vote": "no"}
        )
        assert vote2_response.status_code == 200
        match2 = vote2_response.json()
        voter2 = next((v for v in match2["votes"] if v["user_id"] == user_id), None)
        assert voter2["vote"] == "no"
        
        # Verify only one vote per user
        user_votes = [v for v in match2["votes"] if v["user_id"] == user_id]
        assert len(user_votes) == 1, "Should have only one vote per user"
        
        # Change vote to "reserve"
        vote3_response = api_client.post(
            f"{base_url}/api/matches/{match_id}/vote",
            headers={"Authorization": f"Bearer {token}"},
            json={"vote": "reserve"}
        )
        assert vote3_response.status_code == 200
        match3 = vote3_response.json()
        voter3 = next((v for v in match3["votes"] if v["user_id"] == user_id), None)
        assert voter3["vote"] == "reserve"

    def test_generate_lineup_editor_only_snake_draft_by_rating(self, base_url, api_client, admin_client, test_run_id):
        """POST /api/matches/{id}/generate-lineup (editor only) splits yes voters using snake draft by rating"""
        # Create match
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Lineup Generation Match",
            "date": "2026-04-01T18:00:00Z",
            "team_size": 3
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Create 8 users with different ratings and have them vote
        users = []
        for i in range(8):
            reg_response = api_client.post(f"{base_url}/api/auth/register", json={
                "email": f"TEST_player{i}_{test_run_id}@clubdodo.com",
                "password": "testpass123",
                "name": f"Player {i}",
                "shirt_number": i + 1
            })
            assert reg_response.status_code == 200
            token = reg_response.json()["token"]
            user_id = reg_response.json()["user"]["id"]
            users.append({"id": user_id, "token": token, "name": f"Player {i}"})
            
            # Vote yes for first 7, reserve for last one
            vote = "yes" if i < 7 else "reserve"
            vote_response = api_client.post(
                f"{base_url}/api/matches/{match_id}/vote",
                headers={"Authorization": f"Bearer {token}"},
                json={"vote": vote}
            )
            assert vote_response.status_code == 200
        
        # Generate lineup
        lineup_response = admin_client.post(f"{base_url}/api/matches/{match_id}/generate-lineup")
        assert lineup_response.status_code == 200, f"Expected 200, got {lineup_response.status_code}: {lineup_response.text}"
        
        match = lineup_response.json()
        assert match["status"] == "scheduled"
        assert match["lineup"] is not None
        
        lineup = match["lineup"]
        assert "team_a" in lineup
        assert "team_b" in lineup
        assert "reserves" in lineup
        assert lineup["team_size"] == 3
        
        # With team_size=3, we can fit 6 players (3 per team)
        assert len(lineup["team_a"]) == 3
        assert len(lineup["team_b"]) == 3
        # 7 yes votes - 6 on teams = 1 overflow + 1 reserve vote = 2 reserves
        assert len(lineup["reserves"]) == 2
        
        # Verify snake draft pattern (all have rating 0, so order by registration)
        # Snake draft: A, B, B, A, A, B
        # Round 0 (even): pick 0→A, pick 1→B
        # Round 1 (odd):  pick 2→B, pick 3→A
        # Round 2 (even): pick 4→A, pick 5→B

    def test_generate_lineup_non_editor_returns_403(self, base_url, api_client, test_run_id):
        """User without can_edit_matches & not admin cannot generate lineup (403)"""
        # Register regular user
        register_response = api_client.post(f"{base_url}/api/auth/register", json={
            "email": f"TEST_non_editor_{test_run_id}@clubdodo.com",
            "password": "testpass123",
            "name": "Non Editor"
        })
        assert register_response.status_code == 200
        token = register_response.json()["token"]
        
        # Create match
        match_response = api_client.post(
            f"{base_url}/api/matches",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "title": "TEST Non-editor Match",
                "date": "2026-04-05T18:00:00Z",
                "team_size": 5
            }
        )
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Try to generate lineup
        lineup_response = api_client.post(
            f"{base_url}/api/matches/{match_id}/generate-lineup",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert lineup_response.status_code == 403, f"Expected 403, got {lineup_response.status_code}"

    def test_record_result_editor_only_updates_stats_and_rating(self, base_url, api_client, admin_client, test_run_id):
        """POST /api/matches/{id}/result (editor only) records goals/assists, updates stats and rating"""
        # Create match
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Result Recording Match",
            "date": "2026-04-10T18:00:00Z",
            "team_size": 3
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Create 4 players and have them vote
        players = []
        for i in range(4):
            reg_response = api_client.post(f"{base_url}/api/auth/register", json={
                "email": f"TEST_result_player{i}_{test_run_id}@clubdodo.com",
                "password": "testpass123",
                "name": f"Result Player {i}",
                "shirt_number": 10 + i
            })
            assert reg_response.status_code == 200
            token = reg_response.json()["token"]
            user_id = reg_response.json()["user"]["id"]
            players.append({"id": user_id, "token": token, "name": f"Result Player {i}"})
            
            vote_response = api_client.post(
                f"{base_url}/api/matches/{match_id}/vote",
                headers={"Authorization": f"Bearer {token}"},
                json={"vote": "yes"}
            )
            assert vote_response.status_code == 200
        
        # Generate lineup
        lineup_response = admin_client.post(f"{base_url}/api/matches/{match_id}/generate-lineup")
        assert lineup_response.status_code == 200
        
        # Record result: Player 0 scores 2 goals, Player 1 gets 1 assist, Player 2 scores 1 goal
        result_response = admin_client.post(f"{base_url}/api/matches/{match_id}/result", json={
            "team_a_score": 3,
            "team_b_score": 1,
            "stats": [
                {"user_id": players[0]["id"], "goals": 2, "assists": 0},
                {"user_id": players[1]["id"], "goals": 0, "assists": 1},
                {"user_id": players[2]["id"], "goals": 1, "assists": 0}
            ]
        })
        assert result_response.status_code == 200, f"Expected 200, got {result_response.status_code}: {result_response.text}"
        
        match = result_response.json()
        assert match["status"] == "played"
        assert match["result"] is not None
        assert match["result"]["team_a_score"] == 3
        assert match["result"]["team_b_score"] == 1
        
        # Verify player stats updated
        # Player 0: 2 goals, 0 assists, 1 match → rating = 2*3 + 0*2 + 1 = 7
        player0_response = api_client.get(
            f"{base_url}/api/auth/me",
            headers={"Authorization": f"Bearer {players[0]['token']}"}
        )
        assert player0_response.status_code == 200
        player0 = player0_response.json()
        assert player0["goals"] == 2
        assert player0["assists"] == 0
        assert player0["matches_played"] == 1
        assert player0["rating"] == 7.0, f"Expected rating 7.0, got {player0['rating']}"
        
        # Player 1: 0 goals, 1 assist, 1 match → rating = 0*3 + 1*2 + 1 = 3
        player1_response = api_client.get(
            f"{base_url}/api/auth/me",
            headers={"Authorization": f"Bearer {players[1]['token']}"}
        )
        assert player1_response.status_code == 200
        player1 = player1_response.json()
        assert player1["goals"] == 0
        assert player1["assists"] == 1
        assert player1["matches_played"] == 1
        assert player1["rating"] == 3.0, f"Expected rating 3.0, got {player1['rating']}"
        
        # Player 2: 1 goal, 0 assists, 1 match → rating = 1*3 + 0*2 + 1 = 4
        player2_response = api_client.get(
            f"{base_url}/api/auth/me",
            headers={"Authorization": f"Bearer {players[2]['token']}"}
        )
        assert player2_response.status_code == 200
        player2 = player2_response.json()
        assert player2["goals"] == 1
        assert player2["assists"] == 0
        assert player2["matches_played"] == 1
        assert player2["rating"] == 4.0, f"Expected rating 4.0, got {player2['rating']}"
        
        # Player 3: no stats but played → rating = 0*3 + 0*2 + 1 = 1
        player3_response = api_client.get(
            f"{base_url}/api/auth/me",
            headers={"Authorization": f"Bearer {players[3]['token']}"}
        )
        assert player3_response.status_code == 200
        player3 = player3_response.json()
        assert player3["goals"] == 0
        assert player3["assists"] == 0
        assert player3["matches_played"] == 1
        assert player3["rating"] == 1.0, f"Expected rating 1.0, got {player3['rating']}"

    def test_record_result_editing_reverts_prior_stats(self, base_url, api_client, admin_client, test_run_id):
        """Editing result should revert prior stats before applying new"""
        # Create match with 2 players
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Edit Result Match",
            "date": "2026-04-15T18:00:00Z",
            "team_size": 3
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Create 2 players
        players = []
        for i in range(2):
            reg_response = api_client.post(f"{base_url}/api/auth/register", json={
                "email": f"TEST_edit_player{i}_{test_run_id}@clubdodo.com",
                "password": "testpass123",
                "name": f"Edit Player {i}"
            })
            assert reg_response.status_code == 200
            token = reg_response.json()["token"]
            user_id = reg_response.json()["user"]["id"]
            players.append({"id": user_id, "token": token})
            
            vote_response = api_client.post(
                f"{base_url}/api/matches/{match_id}/vote",
                headers={"Authorization": f"Bearer {token}"},
                json={"vote": "yes"}
            )
            assert vote_response.status_code == 200
        
        # Generate lineup
        admin_client.post(f"{base_url}/api/matches/{match_id}/generate-lineup")
        
        # Record initial result: Player 0 scores 3 goals
        result1_response = admin_client.post(f"{base_url}/api/matches/{match_id}/result", json={
            "team_a_score": 3,
            "team_b_score": 0,
            "stats": [
                {"user_id": players[0]["id"], "goals": 3, "assists": 0}
            ]
        })
        assert result1_response.status_code == 200
        
        # Check Player 0 stats: 3 goals, 1 match → rating = 3*3 + 1 = 10
        player0_check1 = api_client.get(
            f"{base_url}/api/auth/me",
            headers={"Authorization": f"Bearer {players[0]['token']}"}
        )
        assert player0_check1.status_code == 200
        p0_data1 = player0_check1.json()
        assert p0_data1["goals"] == 3
        assert p0_data1["matches_played"] == 1
        assert p0_data1["rating"] == 10.0
        
        # Edit result: Player 0 now has 1 goal, Player 1 has 2 goals
        result2_response = admin_client.post(f"{base_url}/api/matches/{match_id}/result", json={
            "team_a_score": 1,
            "team_b_score": 2,
            "stats": [
                {"user_id": players[0]["id"], "goals": 1, "assists": 0},
                {"user_id": players[1]["id"], "goals": 2, "assists": 0}
            ]
        })
        assert result2_response.status_code == 200
        
        # Check Player 0 stats after edit: should be 1 goal, 1 match → rating = 1*3 + 1 = 4
        player0_check2 = api_client.get(
            f"{base_url}/api/auth/me",
            headers={"Authorization": f"Bearer {players[0]['token']}"}
        )
        assert player0_check2.status_code == 200
        p0_data2 = player0_check2.json()
        assert p0_data2["goals"] == 1, f"Expected 1 goal after edit, got {p0_data2['goals']}"
        assert p0_data2["matches_played"] == 1, f"Expected 1 match, got {p0_data2['matches_played']}"
        assert p0_data2["rating"] == 4.0, f"Expected rating 4.0, got {p0_data2['rating']}"
        
        # Check Player 1 stats: 2 goals, 1 match → rating = 2*3 + 1 = 7
        player1_check = api_client.get(
            f"{base_url}/api/auth/me",
            headers={"Authorization": f"Bearer {players[1]['token']}"}
        )
        assert player1_check.status_code == 200
        p1_data = player1_check.json()
        assert p1_data["goals"] == 2
        assert p1_data["matches_played"] == 1
        assert p1_data["rating"] == 7.0

    def test_record_result_non_editor_returns_403(self, base_url, api_client, test_run_id):
        """User without can_edit_matches & not admin cannot record result (403)"""
        # Register regular user
        register_response = api_client.post(f"{base_url}/api/auth/register", json={
            "email": f"TEST_non_editor_result_{test_run_id}@clubdodo.com",
            "password": "testpass123",
            "name": "Non Editor Result"
        })
        assert register_response.status_code == 200
        token = register_response.json()["token"]
        
        # Create match
        match_response = api_client.post(
            f"{base_url}/api/matches",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "title": "TEST Non-editor Result Match",
                "date": "2026-04-20T18:00:00Z",
                "team_size": 5
            }
        )
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Try to record result
        result_response = api_client.post(
            f"{base_url}/api/matches/{match_id}/result",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "team_a_score": 3,
                "team_b_score": 2,
                "stats": []
            }
        )
        assert result_response.status_code == 403, f"Expected 403, got {result_response.status_code}"

    def test_delete_match_editor_only_reverts_stats(self, base_url, api_client, admin_client, test_run_id):
        """DELETE /api/matches/{id} (editor only) removes match and reverts stat contributions"""
        # Create match
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Delete Match",
            "date": "2026-04-25T18:00:00Z",
            "team_size": 3
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Create 2 players
        players = []
        for i in range(2):
            reg_response = api_client.post(f"{base_url}/api/auth/register", json={
                "email": f"TEST_delete_player{i}_{test_run_id}@clubdodo.com",
                "password": "testpass123",
                "name": f"Delete Player {i}"
            })
            assert reg_response.status_code == 200
            token = reg_response.json()["token"]
            user_id = reg_response.json()["user"]["id"]
            players.append({"id": user_id, "token": token})
            
            vote_response = api_client.post(
                f"{base_url}/api/matches/{match_id}/vote",
                headers={"Authorization": f"Bearer {token}"},
                json={"vote": "yes"}
            )
            assert vote_response.status_code == 200
        
        # Generate lineup and record result
        admin_client.post(f"{base_url}/api/matches/{match_id}/generate-lineup")
        admin_client.post(f"{base_url}/api/matches/{match_id}/result", json={
            "team_a_score": 2,
            "team_b_score": 0,
            "stats": [
                {"user_id": players[0]["id"], "goals": 2, "assists": 0}
            ]
        })
        
        # Verify Player 0 has stats
        player0_before = api_client.get(
            f"{base_url}/api/auth/me",
            headers={"Authorization": f"Bearer {players[0]['token']}"}
        )
        assert player0_before.status_code == 200
        p0_before = player0_before.json()
        assert p0_before["goals"] == 2
        assert p0_before["matches_played"] == 1
        assert p0_before["rating"] == 7.0
        
        # Delete match
        delete_response = admin_client.delete(f"{base_url}/api/matches/{match_id}")
        assert delete_response.status_code == 200, f"Expected 200, got {delete_response.status_code}: {delete_response.text}"
        
        # Verify match is deleted
        get_response = admin_client.get(f"{base_url}/api/matches/{match_id}")
        assert get_response.status_code == 404
        
        # Verify Player 0 stats reverted
        player0_after = api_client.get(
            f"{base_url}/api/auth/me",
            headers={"Authorization": f"Bearer {players[0]['token']}"}
        )
        assert player0_after.status_code == 200
        p0_after = player0_after.json()
        assert p0_after["goals"] == 0, f"Expected 0 goals after delete, got {p0_after['goals']}"
        assert p0_after["matches_played"] == 0, f"Expected 0 matches after delete, got {p0_after['matches_played']}"
        assert p0_after["rating"] == 0.0, f"Expected rating 0.0 after delete, got {p0_after['rating']}"

    def test_delete_match_non_editor_returns_403(self, base_url, api_client, test_run_id):
        """Non-editor cannot delete match (403)"""
        # Register regular user
        register_response = api_client.post(f"{base_url}/api/auth/register", json={
            "email": f"TEST_non_editor_delete_{test_run_id}@clubdodo.com",
            "password": "testpass123",
            "name": "Non Editor Delete"
        })
        assert register_response.status_code == 200
        token = register_response.json()["token"]
        
        # Create match
        match_response = api_client.post(
            f"{base_url}/api/matches",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "title": "TEST Non-editor Delete Match",
                "date": "2026-04-30T18:00:00Z",
                "team_size": 5
            }
        )
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Try to delete match
        delete_response = api_client.delete(
            f"{base_url}/api/matches/{match_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert delete_response.status_code == 403, f"Expected 403, got {delete_response.status_code}"
