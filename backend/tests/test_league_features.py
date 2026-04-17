import pytest
import requests

class TestLeagueFeatures:
    """Tests for league points, 3-team matches, and new user/match fields"""

    # ========== User Fields Tests ==========
    
    def test_register_with_preferred_position_persists(self, base_url, api_client, test_run_id):
        """POST /api/auth/register accepts preferred_position (GK/DEF/MID/FWD/ANY) and persists it"""
        positions = ["GK", "DEF", "MID", "FWD", "ANY"]
        
        for i, position in enumerate(positions):
            payload = {
                "email": f"TEST_position_{position}_{test_run_id}@clubdodo.com",
                "password": "testpass123",
                "name": f"Player {position}",
                "shirt_number": i + 1,
                "preferred_position": position
            }
            response = api_client.post(f"{base_url}/api/auth/register", json=payload)
            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            
            user = response.json()["user"]
            assert user["preferred_position"] == position, f"Expected preferred_position={position}, got {user.get('preferred_position')}"
            assert "_id" not in user
            
            # Verify persistence with GET /api/auth/me
            token = response.json()["token"]
            me_response = api_client.get(
                f"{base_url}/api/auth/me",
                headers={"Authorization": f"Bearer {token}"}
            )
            assert me_response.status_code == 200
            me_data = me_response.json()
            assert me_data["preferred_position"] == position

    def test_register_without_preferred_position_defaults_to_none(self, base_url, api_client, test_run_id):
        """POST /api/auth/register without preferred_position defaults to None"""
        payload = {
            "email": f"TEST_no_position_{test_run_id}@clubdodo.com",
            "password": "testpass123",
            "name": "No Position Player"
        }
        response = api_client.post(f"{base_url}/api/auth/register", json=payload)
        assert response.status_code == 200
        
        user = response.json()["user"]
        assert user.get("preferred_position") is None

    def test_auth_me_returns_new_league_fields(self, base_url, api_client, test_run_id):
        """GET /api/auth/me returns new fields: preferred_position, wins, draws, losses, league_points"""
        payload = {
            "email": f"TEST_league_fields_{test_run_id}@clubdodo.com",
            "password": "testpass123",
            "name": "League Player",
            "preferred_position": "MID"
        }
        register_response = api_client.post(f"{base_url}/api/auth/register", json=payload)
        assert register_response.status_code == 200
        token = register_response.json()["token"]
        
        me_response = api_client.get(
            f"{base_url}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert me_response.status_code == 200
        
        user = me_response.json()
        assert "preferred_position" in user
        assert user["preferred_position"] == "MID"
        assert "wins" in user
        assert user["wins"] == 0
        assert "draws" in user
        assert user["draws"] == 0
        assert "losses" in user
        assert user["losses"] == 0
        assert "league_points" in user
        assert user["league_points"] == 0
        assert "_id" not in user

    def test_put_users_me_updates_preferred_position(self, base_url, api_client, test_run_id):
        """PUT /api/users/me updates preferred_position"""
        # Register user
        register_response = api_client.post(f"{base_url}/api/auth/register", json={
            "email": f"TEST_update_position_{test_run_id}@clubdodo.com",
            "password": "testpass123",
            "name": "Position Changer",
            "preferred_position": "DEF"
        })
        assert register_response.status_code == 200
        token = register_response.json()["token"]
        
        # Update preferred_position
        update_response = api_client.put(
            f"{base_url}/api/users/me",
            headers={"Authorization": f"Bearer {token}"},
            json={"preferred_position": "FWD"}
        )
        assert update_response.status_code == 200, f"Expected 200, got {update_response.status_code}: {update_response.text}"
        
        updated_user = update_response.json()
        assert updated_user["preferred_position"] == "FWD"
        
        # Verify persistence
        me_response = api_client.get(
            f"{base_url}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert me_response.status_code == 200
        assert me_response.json()["preferred_position"] == "FWD"

    # ========== Match Type & Third Team Tests ==========
    
    def test_post_matches_accepts_match_type_and_third_team_enabled(self, base_url, admin_client):
        """POST /api/matches accepts match_type ('friendly'|'league') and third_team_enabled (bool)"""
        # Test league match
        league_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST League Match",
            "date": "2026-05-01T19:00:00Z",
            "team_size": 5,
            "match_type": "league",
            "third_team_enabled": False
        })
        assert league_response.status_code == 200, f"Expected 200, got {league_response.status_code}: {league_response.text}"
        
        league_match = league_response.json()
        assert league_match["match_type"] == "league"
        assert league_match["third_team_enabled"] == False
        assert "_id" not in league_match
        
        # Test friendly match with 3 teams
        friendly_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST 3-Team Friendly",
            "date": "2026-05-02T19:00:00Z",
            "team_size": 4,
            "match_type": "friendly",
            "third_team_enabled": True
        })
        assert friendly_response.status_code == 200
        
        friendly_match = friendly_response.json()
        assert friendly_match["match_type"] == "friendly"
        assert friendly_match["third_team_enabled"] == True

    def test_post_matches_defaults_to_friendly_and_no_third_team(self, base_url, admin_client):
        """POST /api/matches defaults to match_type='friendly' and third_team_enabled=false"""
        response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Default Match",
            "date": "2026-05-03T19:00:00Z",
            "team_size": 5
        })
        assert response.status_code == 200
        
        match = response.json()
        assert match["match_type"] == "friendly"
        assert match["third_team_enabled"] == False

    def test_get_match_returns_match_type_and_third_team_enabled(self, base_url, admin_client):
        """GET /api/matches/{id} returns match_type and third_team_enabled"""
        # Create match
        create_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Get Match Fields",
            "date": "2026-05-04T19:00:00Z",
            "team_size": 5,
            "match_type": "league",
            "third_team_enabled": False
        })
        assert create_response.status_code == 200
        match_id = create_response.json()["id"]
        
        # Get match
        get_response = admin_client.get(f"{base_url}/api/matches/{match_id}")
        assert get_response.status_code == 200
        
        match = get_response.json()
        assert match["match_type"] == "league"
        assert match["third_team_enabled"] == False
        assert "_id" not in match

    # ========== 3-Team Lineup Tests ==========
    
    def test_generate_lineup_with_third_team_enabled_produces_team_c(self, base_url, api_client, admin_client, test_run_id):
        """POST /api/matches/{id}/generate-lineup with third_team_enabled=true produces team_a, team_b, team_c"""
        # Create 3-team match
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST 3-Team Lineup",
            "date": "2026-05-05T19:00:00Z",
            "team_size": 3,
            "match_type": "friendly",
            "third_team_enabled": True
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Create 10 players and have them vote yes
        players = []
        for i in range(10):
            reg_response = api_client.post(f"{base_url}/api/auth/register", json={
                "email": f"TEST_3team_player{i}_{test_run_id}@clubdodo.com",
                "password": "testpass123",
                "name": f"3Team Player {i}",
                "shirt_number": 20 + i
            })
            assert reg_response.status_code == 200
            token = reg_response.json()["token"]
            players.append(token)
            
            vote_response = api_client.post(
                f"{base_url}/api/matches/{match_id}/vote",
                headers={"Authorization": f"Bearer {token}"},
                json={"vote": "yes"}
            )
            assert vote_response.status_code == 200
        
        # Generate lineup
        lineup_response = admin_client.post(f"{base_url}/api/matches/{match_id}/generate-lineup")
        assert lineup_response.status_code == 200, f"Expected 200, got {lineup_response.status_code}: {lineup_response.text}"
        
        match = lineup_response.json()
        lineup = match["lineup"]
        
        assert "team_a" in lineup
        assert "team_b" in lineup
        assert "team_c" in lineup
        assert lineup["third_team_enabled"] == True
        
        # With team_size=3 and 3 teams, we can fit 9 players (3 per team)
        assert len(lineup["team_a"]) == 3, f"Expected 3 players in team_a, got {len(lineup['team_a'])}"
        assert len(lineup["team_b"]) == 3, f"Expected 3 players in team_b, got {len(lineup['team_b'])}"
        assert len(lineup["team_c"]) == 3, f"Expected 3 players in team_c, got {len(lineup['team_c'])}"
        # 10 yes votes - 9 on teams = 1 in reserves
        assert len(lineup["reserves"]) == 1, f"Expected 1 player in reserves, got {len(lineup['reserves'])}"

    def test_generate_lineup_without_third_team_produces_empty_team_c(self, base_url, api_client, admin_client, test_run_id):
        """POST /api/matches/{id}/generate-lineup with third_team_enabled=false produces empty team_c array"""
        # Create 2-team match
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST 2-Team Lineup",
            "date": "2026-05-06T19:00:00Z",
            "team_size": 3,
            "match_type": "league",
            "third_team_enabled": False
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Create 6 players and have them vote yes
        for i in range(6):
            reg_response = api_client.post(f"{base_url}/api/auth/register", json={
                "email": f"TEST_2team_player{i}_{test_run_id}@clubdodo.com",
                "password": "testpass123",
                "name": f"2Team Player {i}"
            })
            assert reg_response.status_code == 200
            token = reg_response.json()["token"]
            
            vote_response = api_client.post(
                f"{base_url}/api/matches/{match_id}/vote",
                headers={"Authorization": f"Bearer {token}"},
                json={"vote": "yes"}
            )
            assert vote_response.status_code == 200
        
        # Generate lineup
        lineup_response = admin_client.post(f"{base_url}/api/matches/{match_id}/generate-lineup")
        assert lineup_response.status_code == 200
        
        match = lineup_response.json()
        lineup = match["lineup"]
        
        assert len(lineup["team_a"]) == 3
        assert len(lineup["team_b"]) == 3
        assert lineup["team_c"] == [], f"Expected empty team_c array, got {lineup['team_c']}"
        assert lineup["third_team_enabled"] == False

    # ========== League Points Tests ==========
    
    def test_record_result_league_match_awards_league_points_winner_3_loser_0(self, base_url, api_client, admin_client, test_run_id):
        """POST /api/matches/{id}/result with match_type='league' awards winner +3 league_points +1 win, loser +1 loss"""
        # Create league match
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST League Points Win",
            "date": "2026-05-10T19:00:00Z",
            "team_size": 3,
            "match_type": "league",
            "third_team_enabled": False
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Create 6 players
        players = []
        for i in range(4):
            reg_response = api_client.post(f"{base_url}/api/auth/register", json={
                "email": f"TEST_league_win_player{i}_{test_run_id}@clubdodo.com",
                "password": "testpass123",
                "name": f"League Win Player {i}"
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
        lineup_response = admin_client.post(f"{base_url}/api/matches/{match_id}/generate-lineup")
        assert lineup_response.status_code == 200
        lineup = lineup_response.json()["lineup"]
        
        team_a_ids = [p["user_id"] for p in lineup["team_a"]]
        team_b_ids = [p["user_id"] for p in lineup["team_b"]]
        
        # Record result: Team A wins 3-1
        result_response = admin_client.post(f"{base_url}/api/matches/{match_id}/result", json={
            "team_a_score": 3,
            "team_b_score": 1,
            "stats": []
        })
        assert result_response.status_code == 200, f"Expected 200, got {result_response.status_code}: {result_response.text}"
        
        # Verify Team A players (winners) have +3 league_points, +1 win
        for player_id in team_a_ids:
            player_token = next(p["token"] for p in players if p["id"] == player_id)
            me_response = api_client.get(
                f"{base_url}/api/auth/me",
                headers={"Authorization": f"Bearer {player_token}"}
            )
            assert me_response.status_code == 200
            user = me_response.json()
            assert user["league_points"] == 3, f"Winner should have 3 league_points, got {user['league_points']}"
            assert user["wins"] == 1, f"Winner should have 1 win, got {user['wins']}"
            assert user["draws"] == 0
            assert user["losses"] == 0
        
        # Verify Team B players (losers) have 0 league_points, +1 loss
        for player_id in team_b_ids:
            player_token = next(p["token"] for p in players if p["id"] == player_id)
            me_response = api_client.get(
                f"{base_url}/api/auth/me",
                headers={"Authorization": f"Bearer {player_token}"}
            )
            assert me_response.status_code == 200
            user = me_response.json()
            assert user["league_points"] == 0, f"Loser should have 0 league_points, got {user['league_points']}"
            assert user["wins"] == 0
            assert user["draws"] == 0
            assert user["losses"] == 1, f"Loser should have 1 loss, got {user['losses']}"

    def test_record_result_league_match_draw_awards_1_point_each(self, base_url, api_client, admin_client, test_run_id):
        """POST /api/matches/{id}/result with match_type='league' and draw awards +1 league_points +1 draw to both teams"""
        # Create league match
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST League Points Draw",
            "date": "2026-05-11T19:00:00Z",
            "team_size": 3,
            "match_type": "league",
            "third_team_enabled": False
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Create 6 players
        players = []
        for i in range(6):
            reg_response = api_client.post(f"{base_url}/api/auth/register", json={
                "email": f"TEST_league_draw_player{i}_{test_run_id}@clubdodo.com",
                "password": "testpass123",
                "name": f"League Draw Player {i}"
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
        lineup_response = admin_client.post(f"{base_url}/api/matches/{match_id}/generate-lineup")
        assert lineup_response.status_code == 200
        
        # Record result: Draw 2-2
        result_response = admin_client.post(f"{base_url}/api/matches/{match_id}/result", json={
            "team_a_score": 2,
            "team_b_score": 2,
            "stats": []
        })
        assert result_response.status_code == 200
        
        # Verify all players have +1 league_points, +1 draw
        for player in players:
            me_response = api_client.get(
                f"{base_url}/api/auth/me",
                headers={"Authorization": f"Bearer {player['token']}"}
            )
            assert me_response.status_code == 200
            user = me_response.json()
            assert user["league_points"] == 1, f"Draw should give 1 league_point, got {user['league_points']}"
            assert user["wins"] == 0
            assert user["draws"] == 1, f"Draw should give 1 draw, got {user['draws']}"
            assert user["losses"] == 0

    def test_record_result_friendly_match_does_not_award_league_points(self, base_url, api_client, admin_client, test_run_id):
        """POST /api/matches/{id}/result with match_type='friendly' does NOT award league points"""
        # Create friendly match
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Friendly No Points",
            "date": "2026-05-12T19:00:00Z",
            "team_size": 3,
            "match_type": "friendly",
            "third_team_enabled": False
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Create 6 players
        players = []
        for i in range(6):
            reg_response = api_client.post(f"{base_url}/api/auth/register", json={
                "email": f"TEST_friendly_player{i}_{test_run_id}@clubdodo.com",
                "password": "testpass123",
                "name": f"Friendly Player {i}"
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
        
        # Record result: Team A wins 5-0
        result_response = admin_client.post(f"{base_url}/api/matches/{match_id}/result", json={
            "team_a_score": 5,
            "team_b_score": 0,
            "stats": []
        })
        assert result_response.status_code == 200
        
        # Verify NO league points awarded (all should be 0)
        for player in players:
            me_response = api_client.get(
                f"{base_url}/api/auth/me",
                headers={"Authorization": f"Bearer {player['token']}"}
            )
            assert me_response.status_code == 200
            user = me_response.json()
            assert user["league_points"] == 0, f"Friendly match should not award league_points, got {user['league_points']}"
            assert user["wins"] == 0, f"Friendly match should not track wins, got {user['wins']}"
            assert user["draws"] == 0
            assert user["losses"] == 0

    def test_edit_league_match_result_reverts_prior_league_points(self, base_url, api_client, admin_client, test_run_id):
        """Editing a league match result reverts prior league points before applying new outcome"""
        # Create league match
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Edit League Result",
            "date": "2026-05-13T19:00:00Z",
            "team_size": 3,
            "match_type": "league",
            "third_team_enabled": False
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Create 6 players
        players = []
        for i in range(6):
            reg_response = api_client.post(f"{base_url}/api/auth/register", json={
                "email": f"TEST_edit_league_player{i}_{test_run_id}@clubdodo.com",
                "password": "testpass123",
                "name": f"Edit League Player {i}"
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
        lineup_response = admin_client.post(f"{base_url}/api/matches/{match_id}/generate-lineup")
        lineup = lineup_response.json()["lineup"]
        team_a_ids = [p["user_id"] for p in lineup["team_a"]]
        team_b_ids = [p["user_id"] for p in lineup["team_b"]]
        
        # Record initial result: Team A wins 3-1
        result1_response = admin_client.post(f"{base_url}/api/matches/{match_id}/result", json={
            "team_a_score": 3,
            "team_b_score": 1,
            "stats": []
        })
        assert result1_response.status_code == 200
        
        # Verify Team A has 3 points, Team B has 0
        team_a_token = next(p["token"] for p in players if p["id"] == team_a_ids[0])
        me1 = api_client.get(f"{base_url}/api/auth/me", headers={"Authorization": f"Bearer {team_a_token}"})
        assert me1.json()["league_points"] == 3
        assert me1.json()["wins"] == 1
        
        # Edit result: Now it's a draw 2-2
        result2_response = admin_client.post(f"{base_url}/api/matches/{match_id}/result", json={
            "team_a_score": 2,
            "team_b_score": 2,
            "stats": []
        })
        assert result2_response.status_code == 200
        
        # Verify Team A now has 1 point (draw), not 4 (3+1)
        me2 = api_client.get(f"{base_url}/api/auth/me", headers={"Authorization": f"Bearer {team_a_token}"})
        user_after = me2.json()
        assert user_after["league_points"] == 1, f"After edit to draw, should have 1 point, got {user_after['league_points']}"
        assert user_after["wins"] == 0, f"After edit to draw, should have 0 wins, got {user_after['wins']}"
        assert user_after["draws"] == 1, f"After edit to draw, should have 1 draw, got {user_after['draws']}"
        assert user_after["losses"] == 0

    def test_delete_league_match_reverts_league_points(self, base_url, api_client, admin_client, test_run_id):
        """DELETE /api/matches/{id} on played league match reverts league points for all participants"""
        # Create league match
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST Delete League Match",
            "date": "2026-05-14T19:00:00Z",
            "team_size": 3,
            "match_type": "league",
            "third_team_enabled": False
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Create 6 players
        players = []
        for i in range(6):
            reg_response = api_client.post(f"{base_url}/api/auth/register", json={
                "email": f"TEST_delete_league_player{i}_{test_run_id}@clubdodo.com",
                "password": "testpass123",
                "name": f"Delete League Player {i}"
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
            "team_a_score": 4,
            "team_b_score": 2,
            "stats": []
        })
        
        # Verify players have league points
        me_before = api_client.get(f"{base_url}/api/auth/me", headers={"Authorization": f"Bearer {players[0]['token']}"})
        user_before = me_before.json()
        initial_points = user_before["league_points"]
        assert initial_points > 0, "Should have league points before delete"
        
        # Delete match
        delete_response = admin_client.delete(f"{base_url}/api/matches/{match_id}")
        assert delete_response.status_code == 200
        
        # Verify league points reverted
        for player in players:
            me_after = api_client.get(f"{base_url}/api/auth/me", headers={"Authorization": f"Bearer {player['token']}"})
            user_after = me_after.json()
            assert user_after["league_points"] == 0, f"League points should be reverted to 0, got {user_after['league_points']}"
            assert user_after["wins"] == 0
            assert user_after["draws"] == 0
            assert user_after["losses"] == 0
            assert user_after["matches_played"] == 0

    # ========== 3-Team Match Result Tests ==========
    
    def test_record_result_3team_match_accepts_team_c_score(self, base_url, api_client, admin_client, test_run_id):
        """POST /api/matches/{id}/result accepts team_c_score when third_team_enabled=true"""
        # Create 3-team match
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST 3-Team Result",
            "date": "2026-05-15T19:00:00Z",
            "team_size": 3,
            "match_type": "friendly",
            "third_team_enabled": True
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Create 6 players
        for i in range(6):
            reg_response = api_client.post(f"{base_url}/api/auth/register", json={
                "email": f"TEST_3team_result_player{i}_{test_run_id}@clubdodo.com",
                "password": "testpass123",
                "name": f"3Team Result Player {i}"
            })
            assert reg_response.status_code == 200
            token = reg_response.json()["token"]
            
            vote_response = api_client.post(
                f"{base_url}/api/matches/{match_id}/vote",
                headers={"Authorization": f"Bearer {token}"},
                json={"vote": "yes"}
            )
            assert vote_response.status_code == 200
        
        # Generate lineup
        admin_client.post(f"{base_url}/api/matches/{match_id}/generate-lineup")
        
        # Record result with team_c_score
        result_response = admin_client.post(f"{base_url}/api/matches/{match_id}/result", json={
            "team_a_score": 3,
            "team_b_score": 2,
            "team_c_score": 4,
            "stats": []
        })
        assert result_response.status_code == 200, f"Expected 200, got {result_response.status_code}: {result_response.text}"
        
        match = result_response.json()
        result = match["result"]
        assert result["team_a_score"] == 3
        assert result["team_b_score"] == 2
        assert result["team_c_score"] == 4, f"Expected team_c_score=4, got {result.get('team_c_score')}"

    def test_3team_match_increments_matches_played_for_all_3_teams(self, base_url, api_client, admin_client, test_run_id):
        """3-team match: matches_played is incremented for team_a + team_b + team_c participants"""
        # Create 3-team match
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST 3-Team Matches Played",
            "date": "2026-05-16T19:00:00Z",
            "team_size": 3,
            "match_type": "friendly",
            "third_team_enabled": True
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Create 6 players
        players = []
        for i in range(6):
            reg_response = api_client.post(f"{base_url}/api/auth/register", json={
                "email": f"TEST_3team_played_player{i}_{test_run_id}@clubdodo.com",
                "password": "testpass123",
                "name": f"3Team Played Player {i}"
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
        lineup_response = admin_client.post(f"{base_url}/api/matches/{match_id}/generate-lineup")
        lineup = lineup_response.json()["lineup"]
        
        # Verify lineup has all 3 teams populated
        assert len(lineup["team_a"]) == 2
        assert len(lineup["team_b"]) == 2
        assert len(lineup["team_c"]) == 2
        
        # Record result
        result_response = admin_client.post(f"{base_url}/api/matches/{match_id}/result", json={
            "team_a_score": 1,
            "team_b_score": 2,
            "team_c_score": 3,
            "stats": []
        })
        assert result_response.status_code == 200
        
        # Verify all 6 players have matches_played incremented
        for player in players:
            me_response = api_client.get(
                f"{base_url}/api/auth/me",
                headers={"Authorization": f"Bearer {player['token']}"}
            )
            assert me_response.status_code == 200
            user = me_response.json()
            assert user["matches_played"] == 1, f"All 6 players should have matches_played=1, got {user['matches_played']}"
            # Verify NO league points for 3-team match (even if it were league type, 3-team is friendly-only)
            assert user["league_points"] == 0
            assert user["wins"] == 0
            assert user["draws"] == 0
            assert user["losses"] == 0

    def test_3team_league_match_does_not_award_league_points(self, base_url, api_client, admin_client, test_run_id):
        """3-team match with match_type='league' should NOT award league points (3-team is friendly-only)"""
        # Create 3-team league match (edge case - should be treated as friendly for points)
        match_response = admin_client.post(f"{base_url}/api/matches", json={
            "title": "TEST 3-Team League Edge Case",
            "date": "2026-05-17T19:00:00Z",
            "team_size": 3,
            "match_type": "league",
            "third_team_enabled": True
        })
        assert match_response.status_code == 200
        match_id = match_response.json()["id"]
        
        # Create 6 players
        players = []
        for i in range(6):
            reg_response = api_client.post(f"{base_url}/api/auth/register", json={
                "email": f"TEST_3team_league_player{i}_{test_run_id}@clubdodo.com",
                "password": "testpass123",
                "name": f"3Team League Player {i}"
            })
            assert reg_response.status_code == 200
            token = reg_response.json()["token"]
            players.append({"token": token})
            
            vote_response = api_client.post(
                f"{base_url}/api/matches/{match_id}/vote",
                headers={"Authorization": f"Bearer {token}"},
                json={"vote": "yes"}
            )
            assert vote_response.status_code == 200
        
        # Generate lineup and record result
        admin_client.post(f"{base_url}/api/matches/{match_id}/generate-lineup")
        admin_client.post(f"{base_url}/api/matches/{match_id}/result", json={
            "team_a_score": 5,
            "team_b_score": 3,
            "team_c_score": 1,
            "stats": []
        })
        
        # Verify NO league points awarded (3-team matches don't award league points)
        for player in players:
            me_response = api_client.get(
                f"{base_url}/api/auth/me",
                headers={"Authorization": f"Bearer {player['token']}"}
            )
            assert me_response.status_code == 200
            user = me_response.json()
            assert user["league_points"] == 0, f"3-team match should not award league_points, got {user['league_points']}"
            assert user["wins"] == 0
            assert user["draws"] == 0
            assert user["losses"] == 0
