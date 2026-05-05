import React, { useCallback, useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  Modal,
  KeyboardAvoidingView,
  Platform,
  TextInput,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter, useFocusEffect } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { api } from '../../src/api';
import { useAuth } from '../../src/auth';
import { colors, spacing, radii } from '../../src/theme';
import { Display, Overline, Muted, Title } from '../../src/typography';
import Avatar from '../../src/Avatar';

const TEAM_COLORS = {
  a: { primary: '#DC2626', label: 'RED', text: '#fff' },
  b: { primary: '#18181B', label: 'BLACK', text: '#fff' },
  c: { primary: '#F5F5F4', label: 'WHITE', text: '#111' },
};

type Vote = {
  user_id: string;
  name: string;
  shirt_number: number | null;
  profile_picture: string | null;
  preferred_position?: string | null;
  preferred_positions?: string[];
  rating: number;
  vote: 'yes' | 'no' | 'reserve';
};

type Match = {
  id: string;
  title: string;
  date: string;
  location?: string | null;
  team_size: number;
  match_type: 'friendly' | 'league';
  third_team_enabled: boolean;
  duration_minutes: number;
  timer_started_at: string | null;
  timer_ended_at: string | null;
  status: 'voting' | 'scheduled' | 'in_progress' | 'played' | 'completed';
  created_by?: string;
  score_a?: number;
  score_b?: number;
  score_c?: number;
  tournament_id?: string | null;
  tournament_home?: string | null;
  tournament_away?: string | null;
  votes: Vote[];
  lineup?: {
    team_a: Vote[];
    team_b: Vote[];
    team_c: Vote[];
    reserves: Vote[];
    team_size: number;
    third_team_enabled?: boolean;
  } | null;
  result?: {
    team_a_score: number;
    team_b_score: number;
    team_c_score?: number | null;
    stats: { user_id: string; goals: number; assists: number }[];
  } | null;
  motm?: {
    votes: Record<string, number>;
    winner_id: string | null;
    total: number;
  };
};

type Bucket = 'team_a' | 'team_b' | 'team_c' | 'reserves';

function formatDate(d: string) {
  const dt = new Date(d);
  if (isNaN(dt.getTime())) return d;
  return dt.toLocaleString(undefined, {
    weekday: 'long', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

function formationCoords(n: number): { x: number; y: number }[] {
  // y must stay in [0.55, 0.93] so team A stays in the BOTTOM half, and
  // team B (flipped to 1-y) stays in the TOP half. That guarantees no
  // cross-half overlap and a clean gap around the midline. The 0.93 cap
  // keeps the 44px GK marker + name fully inside the pitch's clip rect.
  // 0.93 = goal line (GK)
  // 0.78 = defenders
  // 0.65 = midfield
  // 0.56 = front-line (just below midline)
  if (n === 3) return [
    { x: 0.5, y: 0.93 },
    { x: 0.3, y: 0.7 }, { x: 0.7, y: 0.7 },
  ];
  if (n === 4) return [
    { x: 0.5, y: 0.93 },
    { x: 0.28, y: 0.78 }, { x: 0.72, y: 0.78 },
    { x: 0.5, y: 0.6 },
  ];
  if (n === 5) return [
    { x: 0.5, y: 0.93 },
    { x: 0.25, y: 0.8 }, { x: 0.75, y: 0.8 },
    { x: 0.32, y: 0.62 }, { x: 0.68, y: 0.62 },
  ];
  if (n === 6) return [
    { x: 0.5, y: 0.93 },
    { x: 0.25, y: 0.82 }, { x: 0.75, y: 0.82 },
    { x: 0.25, y: 0.66 }, { x: 0.75, y: 0.66 },
    { x: 0.5, y: 0.58 },
  ];
  if (n === 7) return [
    { x: 0.5, y: 0.93 },
    { x: 0.2, y: 0.82 }, { x: 0.5, y: 0.82 }, { x: 0.8, y: 0.82 },
    { x: 0.28, y: 0.68 }, { x: 0.72, y: 0.68 },
    { x: 0.5, y: 0.58 },
  ];
  if (n === 8) return [
    // 1-3-3-1
    { x: 0.5, y: 0.93 },
    { x: 0.2, y: 0.83 }, { x: 0.5, y: 0.83 }, { x: 0.8, y: 0.83 },
    { x: 0.22, y: 0.7 }, { x: 0.5, y: 0.7 }, { x: 0.78, y: 0.7 },
    { x: 0.5, y: 0.58 },
  ];
  if (n === 9) return [
    // 1-3-3-2
    { x: 0.5, y: 0.93 },
    { x: 0.2, y: 0.85 }, { x: 0.5, y: 0.85 }, { x: 0.8, y: 0.85 },
    { x: 0.2, y: 0.72 }, { x: 0.5, y: 0.72 }, { x: 0.8, y: 0.72 },
    { x: 0.35, y: 0.58 }, { x: 0.65, y: 0.58 },
  ];
  // n === 11 default 1-4-4-2
  return [
    { x: 0.5, y: 0.93 },
    { x: 0.14, y: 0.85 }, { x: 0.38, y: 0.85 }, { x: 0.62, y: 0.85 }, { x: 0.86, y: 0.85 },
    { x: 0.18, y: 0.72 }, { x: 0.4, y: 0.72 }, { x: 0.6, y: 0.72 }, { x: 0.82, y: 0.72 },
    { x: 0.4, y: 0.58 }, { x: 0.6, y: 0.58 },
  ];
}

function PlayerMarker({ player, x, y, flip, color, textColor, onPress, selected }: {
  player?: Vote; x: number; y: number; flip?: boolean; color: string; textColor: string;
  onPress?: () => void; selected?: boolean;
}) {
  const ay = flip ? 1 - y : y;
  // Name renders below the marker by default; for markers near a goal line,
  // flip it above so the pitch's overflow:hidden doesn't clip it.
  const nameAbove = ay > 0.85 || ay < 0.15;
  if (!player) {
    return <View style={[styles.markerEmpty, { left: `${x * 100}%`, top: `${ay * 100}%`, borderColor: color }]}>
      <Text style={styles.markerEmptyText}>?</Text>
    </View>;
  }
  const Wrapper: any = onPress ? TouchableOpacity : View;
  return (
    <Wrapper
      onPress={onPress}
      activeOpacity={0.75}
      hitSlop={{ top: 6, bottom: 6, left: 6, right: 6 }}
      style={[styles.markerWrap, { left: `${x * 100}%`, top: `${ay * 100}%` }]}
    >
      {/* Name is absolutely positioned so it never shifts the marker anchor. */}
      <Text
        style={[styles.markerName, nameAbove ? styles.markerNameAbove : styles.markerNameBelow]}
        numberOfLines={1}
      >
        {player.name.split(' ')[0]}
      </Text>
      <View
        style={[
          styles.marker,
          { backgroundColor: color, borderColor: selected ? '#fff' : color },
          selected && {
            borderWidth: 3,
            shadowColor: '#fff',
            shadowOpacity: 0.9,
            shadowRadius: 12,
            shadowOffset: { width: 0, height: 0 },
            elevation: 8,
          },
        ]}
      >
        <Text style={[styles.markerNumber, { color: textColor }]}>
          {player.shirt_number ?? player.name.slice(0, 1).toUpperCase()}
        </Text>
      </View>
    </Wrapper>
  );
}

function Stepper({ value, onChange, testID }: { value: number; onChange: (v: number) => void; testID?: string }) {
  return (
    <View style={styles.stepper}>
      <TouchableOpacity
        testID={testID ? `${testID}-dec` : undefined}
        onPress={() => onChange(Math.max(0, value - 1))}
        style={styles.stepperBtn}
        activeOpacity={0.7}
      >
        <Ionicons name="remove" size={18} color={colors.textPrimary} />
      </TouchableOpacity>
      <Text style={styles.stepperValue} testID={testID}>{value}</Text>
      <TouchableOpacity
        testID={testID ? `${testID}-inc` : undefined}
        onPress={() => onChange(value + 1)}
        style={[styles.stepperBtn, styles.stepperBtnPrimary]}
        activeOpacity={0.7}
      >
        <Ionicons name="add" size={18} color="#fff" />
      </TouchableOpacity>
    </View>
  );
}

export default function MatchDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const [match, setMatch] = useState<Match | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [tickTock, setTickTock] = useState(0);
  const [resultOpen, setResultOpen] = useState(false);
  const [scoreA, setScoreA] = useState(0);
  const [scoreB, setScoreB] = useState(0);
  const [scoreC, setScoreC] = useState(0);
  const [playerStats, setPlayerStats] = useState<Record<string, { goals: number; assists: number }>>({});
  const [lineupEditOpen, setLineupEditOpen] = useState(false);
  const [draftBuckets, setDraftBuckets] = useState<Record<string, Bucket>>({});
  const [draftExtras, setDraftExtras] = useState<Vote[]>([]); // added guests or non-lineup users
  const [allUsers, setAllUsers] = useState<any[]>([]);
  const [addPickerOpen, setAddPickerOpen] = useState(false);
  const [guestName, setGuestName] = useState('');
  const [guestShirt, setGuestShirt] = useState('');
  const [guestPosition, setGuestPosition] = useState<string | null>(null);

  // Chat state
  type Comment = {
    id: string;
    match_id: string;
    user_id: string;
    name: string | null;
    profile_picture: string | null;
    text: string;
    created_at: string;
  };
  const [comments, setComments] = useState<Comment[]>([]);
  const [commentDraft, setCommentDraft] = useState('');
  const [postingComment, setPostingComment] = useState(false);

  // Pitch swap mode (tap-to-swap two players on the formation)
  const [pitchSel, setPitchSel] = useState<{ team: 'a' | 'b'; index: number } | null>(null);
  const [swapBusy, setSwapBusy] = useState(false);

  // MOTM state
  type MotmInfo = {
    open: boolean;
    can_vote: boolean;
    candidates: string[];
    my_choice: string | null;
    votes: Record<string, number>;
    winner_id: string | null;
    total: number;
  };
  const [motm, setMotm] = useState<MotmInfo | null>(null);
  const [motmBusy, setMotmBusy] = useState(false);

  // Live in-match score panel
  const [liveBusy, setLiveBusy] = useState(false);
  const liveA = match?.score_a ?? 0;
  const liveB = match?.score_b ?? 0;
  const bumpLive = async (team: 'a' | 'b', delta: 1 | -1) => {
    if (!match || liveBusy) return;
    const nextA = Math.max(0, (match.score_a ?? 0) + (team === 'a' ? delta : 0));
    const nextB = Math.max(0, (match.score_b ?? 0) + (team === 'b' ? delta : 0));
    setLiveBusy(true);
    // Optimistic update
    setMatch({ ...match, score_a: nextA, score_b: nextB } as Match);
    try {
      const updated = await api<Match>(`/matches/${match.id}/live-score`, {
        method: 'POST',
        body: { team_a_score: nextA, team_b_score: nextB },
      });
      setMatch(updated);
    } catch (e: any) {
      // Revert
      setMatch({ ...match });
      Alert.alert('Error', e.message || 'Failed to update score');
    } finally {
      setLiveBusy(false);
    }
  };

  const load = useCallback(async () => {
    if (!id) return;
    try {
      const m = await api<Match>(`/matches/${id}`);
      setMatch(m);
    } catch (e: any) { Alert.alert('Error', e.message || 'Failed to load match'); }
    finally { setLoading(false); }
  }, [id]);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  // Chat: load comments + poll
  const loadComments = useCallback(async () => {
    if (!id) return;
    try {
      const list = await api<Comment[]>(`/matches/${id}/comments`);
      setComments(list);
    } catch {
      /* ignore */
    }
  }, [id]);

  const loadMotm = useCallback(async () => {
    if (!id) return;
    try {
      const m = await api<MotmInfo>(`/matches/${id}/motm`);
      setMotm(m);
    } catch {
      setMotm(null);
    }
  }, [id]);

  useFocusEffect(
    useCallback(() => {
      loadComments();
      loadMotm();
      const t = setInterval(loadComments, 8000);
      return () => clearInterval(t);
    }, [loadComments, loadMotm])
  );

  const castMotm = async (candidateId: string) => {
    setMotmBusy(true);
    try {
      await api(`/matches/${id}/motm/vote`, {
        method: 'POST',
        body: { candidate_id: candidateId },
      });
      await loadMotm();
      await load();
    } catch (e: any) {
      Alert.alert('MOTM vote failed', e.message || 'Try again');
    } finally {
      setMotmBusy(false);
    }
  };

  const postComment = async () => {
    const txt = commentDraft.trim();
    if (!txt) return;
    if (txt.length > 500) {
      Alert.alert('Too long', 'Max 500 characters.');
      return;
    }
    setPostingComment(true);
    try {
      await api(`/matches/${id}/comments`, {
        method: 'POST',
        body: { text: txt },
      });
      setCommentDraft('');
      await loadComments();
    } catch (e: any) {
      Alert.alert('Error', e.message || 'Failed to post');
    } finally {
      setPostingComment(false);
    }
  };

  const deleteComment = async (cid: string) => {
    Alert.alert('Delete message?', 'This cannot be undone.', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          try {
            await api(`/matches/${id}/comments/${cid}`, { method: 'DELETE' });
            setComments((prev) => prev.filter((c) => c.id !== cid));
          } catch (e: any) {
            Alert.alert('Error', e.message || 'Delete failed');
          }
        },
      },
    ]);
  };

  // live timer tick
  useEffect(() => {
    if (!match?.timer_started_at || match?.timer_ended_at) return;
    const t = setInterval(() => setTickTock((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, [match?.timer_started_at, match?.timer_ended_at]);

  const canEdit = !!(user && (user.role === 'admin' || user.can_edit_matches));

  const onPitchTap = useCallback(
    async (team: 'a' | 'b', index: number) => {
      if (!canEdit || !match || !match.lineup) return;
      const teamA = match.lineup.team_a || [];
      const teamB = match.lineup.team_b || [];
      const arrFor = (t: 'a' | 'b') => (t === 'a' ? teamA : teamB);
      if (!pitchSel) {
        if (!arrFor(team)[index]) return;
        setPitchSel({ team, index });
        return;
      }
      if (pitchSel.team === team && pitchSel.index === index) {
        setPitchSel(null);
        return;
      }
      const newA = [...teamA];
      const newB = [...teamB];
      const arrSel = pitchSel.team === 'a' ? newA : newB;
      const arrTarget = team === 'a' ? newA : newB;
      const tmp = arrSel[pitchSel.index];
      arrSel[pitchSel.index] = arrTarget[index];
      arrTarget[index] = tmp;

      const reserves = match.lineup.reserves || [];
      const teamC = match.lineup.team_c || [];
      const buildPayload = (arr: any[]) =>
        arr.filter(Boolean).map((p: any) => {
          if (p.is_guest || (p.user_id || '').startsWith('guest:')) {
            return {
              name: p.name,
              shirt_number: p.shirt_number ?? null,
              preferred_position: p.preferred_position ?? null,
            };
          }
          return p.user_id;
        });
      const payload = {
        team_a: buildPayload(newA),
        team_b: buildPayload(newB),
        team_c: buildPayload(teamC),
        reserves: buildPayload(reserves),
      };

      // Optimistic re-render
      setMatch({
        ...match,
        lineup: { ...match.lineup, team_a: newA, team_b: newB },
      });
      setPitchSel(null);
      setSwapBusy(true);
      try {
        const updated = await api<Match>(`/matches/${match.id}/lineup`, { method: 'PUT', body: payload });
        setMatch(updated);
      } catch (e: any) {
        Alert.alert('Swap failed', e.message || 'Could not save the new lineup');
        load();
      } finally {
        setSwapBusy(false);
      }
    },
    [canEdit, match, pitchSel, load]
  );

  const vote = async (v: 'yes' | 'no' | 'reserve') => {
    if (!match || busy) return;
    setBusy(true);
    try {
      // Toggle: if user re-taps their current vote, clear it instead.
      if (myVote === v) {
        const updated = await api<Match>(`/matches/${match.id}/vote`, { method: 'DELETE' });
        setMatch(updated);
      } else {
        const updated = await api<Match>(`/matches/${match.id}/vote`, { method: 'POST', body: { vote: v } });
        setMatch(updated);
      }
    } catch (e: any) { Alert.alert('Error', e.message || 'Vote failed'); }
    finally { setBusy(false); }
  };

  const generateLineup = async () => {
    if (!match) return;
    setBusy(true);
    try {
      const updated = await api<Match>(`/matches/${match.id}/generate-lineup`, { method: 'POST' });
      setMatch(updated);
    } catch (e: any) { Alert.alert('Error', e.message || 'Failed'); }
    finally { setBusy(false); }
  };

  const timerAction = async (action: 'start' | 'stop' | 'reset') => {
    if (!match) return;
    setBusy(true);
    try {
      const updated = await api<Match>(`/matches/${match.id}/timer/${action}`, { method: 'POST' });
      setMatch(updated);
    } catch (e: any) { Alert.alert('Error', e.message || 'Failed'); }
    finally { setBusy(false); }
  };

  const openResult = () => {
    if (!match) return;
    const existing = match.result;
    if (existing) {
      setScoreA(existing.team_a_score);
      setScoreB(existing.team_b_score);
      setScoreC(existing.team_c_score ?? 0);
      const map: Record<string, { goals: number; assists: number }> = {};
      for (const s of existing.stats) map[s.user_id] = { goals: s.goals, assists: s.assists };
      setPlayerStats(map);
    } else {
      // Seed from live in-flight scores so the recorder doesn't lose progress
      setScoreA(match.score_a ?? 0);
      setScoreB(match.score_b ?? 0);
      setScoreC(match.score_c ?? 0);
      setPlayerStats({});
    }
    setResultOpen(true);
  };

  const saveResult = async () => {
    if (!match) return;
    const stats = Object.entries(playerStats)
      .map(([uid, v]) => ({ user_id: uid, goals: v.goals, assists: v.assists }))
      .filter((s) => s.goals > 0 || s.assists > 0);
    setBusy(true);
    try {
      const body: any = { team_a_score: scoreA, team_b_score: scoreB, stats };
      if (match.third_team_enabled) body.team_c_score = scoreC;
      const updated = await api<Match>(`/matches/${match.id}/result`, { method: 'POST', body });
      setMatch(updated);
      setResultOpen(false);
    } catch (e: any) { Alert.alert('Error', e.message || 'Failed'); }
    finally { setBusy(false); }
  };

  const deleteMatch = async () => {
    if (!match) return;
    Alert.alert('Delete match?', 'This will revert any stats recorded.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: async () => {
        try { await api(`/matches/${match.id}`, { method: 'DELETE' }); router.back(); }
        catch (e: any) { Alert.alert('Error', e.message || 'Failed'); }
      }},
    ]);
  };

  const openLineupEdit = async () => {
    if (!match?.lineup) return;
    const b: Record<string, Bucket> = {};
    for (const p of match.lineup.team_a) b[p.user_id] = 'team_a';
    for (const p of match.lineup.team_b) b[p.user_id] = 'team_b';
    for (const p of match.lineup.team_c) b[p.user_id] = 'team_c';
    for (const p of match.lineup.reserves) b[p.user_id] = 'reserves';
    setDraftBuckets(b);
    setDraftExtras([]);
    try {
      const users = await api<any[]>('/users');
      setAllUsers(users);
    } catch { /* ignore */ }
    setLineupEditOpen(true);
  };

  const addRegisteredToLineup = (u: any) => {
    const entry: Vote = {
      user_id: u.id,
      name: u.name,
      shirt_number: u.shirt_number,
      profile_picture: u.profile_picture,
      preferred_position: u.preferred_position,
      preferred_positions: u.preferred_positions,
      rating: u.rating,
      vote: 'yes',
    };
    setDraftExtras((prev) => [...prev, entry]);
    setDraftBuckets((b) => ({ ...b, [u.id]: 'reserves' }));
    setAddPickerOpen(false);
  };

  const addGuestToLineup = () => {
    if (!guestName.trim()) {
      Alert.alert('Name required', 'Enter a guest name.');
      return;
    }
    const shirt = guestShirt ? parseInt(guestShirt, 10) : null;
    const tempId = `guest:new:${Date.now()}:${Math.random().toString(36).slice(2, 8)}`;
    const entry: Vote & { is_guest?: boolean } = {
      user_id: tempId,
      name: guestName.trim(),
      shirt_number: Number.isFinite(shirt as number) ? (shirt as number) : null,
      profile_picture: null,
      preferred_position: guestPosition,
      preferred_positions: guestPosition ? [guestPosition] : [],
      rating: 0,
      vote: 'yes' as any,
    };
    (entry as any).is_guest = true;
    (entry as any).guest_name = guestName.trim();
    (entry as any).guest_shirt = entry.shirt_number;
    (entry as any).guest_position = guestPosition;
    setDraftExtras((prev) => [...prev, entry]);
    setDraftBuckets((b) => ({ ...b, [tempId]: 'reserves' }));
    setGuestName('');
    setGuestShirt('');
    setGuestPosition(null);
  };

  const removeFromLineup = (uid: string) => {
    setDraftExtras((prev) => prev.filter((p) => p.user_id !== uid));
    setDraftBuckets((b) => {
      const nb = { ...b };
      delete nb[uid];
      return nb;
    });
  };

  const saveLineup = async () => {
    if (!match) return;
    const groups: Record<Bucket, any[]> = { team_a: [], team_b: [], team_c: [], reserves: [] };
    const allPlayers = match.lineup
      ? [...match.lineup.team_a, ...match.lineup.team_b, ...match.lineup.team_c, ...match.lineup.reserves]
      : [];
    const byId: Record<string, any> = {};
    for (const p of allPlayers) byId[p.user_id] = p;
    for (const p of draftExtras) byId[p.user_id] = p;

    for (const [uid, bucket] of Object.entries(draftBuckets)) {
      const src = byId[uid] as any;
      if (!src) continue;
      if (src.is_guest || uid.startsWith('guest:')) {
        // Send as a guest ref; dropping synthetic id so server re-generates
        groups[bucket].push({
          name: src.guest_name || src.name,
          shirt_number: src.guest_shirt ?? src.shirt_number ?? null,
          preferred_position: src.guest_position ?? src.preferred_position ?? null,
        });
      } else {
        groups[bucket].push(uid);
      }
    }
    setBusy(true);
    try {
      const updated = await api<Match>(`/matches/${match.id}/lineup`, { method: 'PUT', body: groups });
      setMatch(updated);
      setLineupEditOpen(false);
    } catch (e: any) { Alert.alert('Error', e.message || 'Failed'); }
    finally { setBusy(false); }
  };

  if (loading || !match) {
    return <SafeAreaView style={styles.safe}><ActivityIndicator color={colors.primary} /></SafeAreaView>;
  }

  const myVote = match.votes.find((v) => v.user_id === user?.id)?.vote;
  const yesVoters = match.votes.filter((v) => v.vote === 'yes');
  const resVoters = match.votes.filter((v) => v.vote === 'reserve');
  const noVoters = match.votes.filter((v) => v.vote === 'no');
  const coords = formationCoords(match.team_size);

  const threeTeam = match.third_team_enabled;
  const teamA = match.lineup?.team_a || [];
  const teamB = match.lineup?.team_b || [];
  const teamC = match.lineup?.team_c || [];
  const allPlayersForResult = match.lineup ? [...teamA, ...teamB, ...teamC] : yesVoters.slice(0, match.team_size * (threeTeam ? 3 : 2));

  // Timer calculations
  let timerSeconds = 0;
  let timerIsRunning = false;
  if (match.timer_started_at) {
    const start = new Date(match.timer_started_at).getTime();
    const end = match.timer_ended_at ? new Date(match.timer_ended_at).getTime() : Date.now();
    timerSeconds = Math.max(0, Math.floor((end - start) / 1000));
    timerIsRunning = !match.timer_ended_at;
  }
  const mm = Math.floor(timerSeconds / 60).toString().padStart(2, '0');
  const ss = (timerSeconds % 60).toString().padStart(2, '0');
  const overtime = timerSeconds > match.duration_minutes * 60;
  // Keep tickTock referenced so ESLint doesn't flag it as unused
  void tickTock;

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.headerRow}>
          <TouchableOpacity testID="back-btn" onPress={() => router.back()} hitSlop={12} style={styles.iconBtn}>
            <Ionicons name="chevron-back" size={22} color={colors.textPrimary} />
          </TouchableOpacity>
          <Overline>{match.status.toUpperCase()}</Overline>
          {canEdit ? (
            <TouchableOpacity testID="delete-match-btn" onPress={deleteMatch} hitSlop={12} style={styles.iconBtn}>
              <Ionicons name="trash-outline" size={20} color={colors.danger} />
            </TouchableOpacity>
          ) : <View style={{ width: 38 }} />}
        </View>

        <Display style={{ fontSize: 34, lineHeight: 36 }}>{match.title}</Display>
        <Muted style={{ marginTop: 4 }}>
          {formatDate(match.date)}{match.location ? ` · ${match.location}` : ''}
        </Muted>
        <View style={styles.chipsRow}>
          <View style={styles.chip}>
            <Text style={styles.chipText}>{match.team_size}v{match.team_size}{threeTeam ? 'v' + match.team_size : ''}</Text>
          </View>
          <View style={styles.chip}>
            <Text style={styles.chipText}>{match.duration_minutes} MIN</Text>
          </View>
          {match.match_type === 'league' ? (
            <View style={[styles.chip, { borderColor: colors.primary }]}>
              <Text style={[styles.chipText, { color: colors.primary }]}>LEAGUE · 3/1/0</Text>
            </View>
          ) : <View style={styles.chip}><Text style={styles.chipText}>FRIENDLY</Text></View>}
          {match.result && (
            <View style={[styles.chip, styles.scoreChip]}>
              <Text style={styles.scoreChipText}>
                {match.result.team_a_score} – {match.result.team_b_score}
                {match.result.team_c_score != null ? ` – ${match.result.team_c_score}` : ''}
              </Text>
            </View>
          )}
        </View>

        {/* Timer card — visible when lineup exists */}
        {match.lineup && (
          <View style={styles.timerCard} testID="match-timer-card">
            <View style={{ flex: 1 }}>
              <Overline>{timerIsRunning ? 'LIVE' : match.timer_started_at ? 'STOPPED' : 'MATCH CLOCK'}</Overline>
              <Text style={[styles.timerDigits, overtime && { color: colors.danger }]} testID="timer-digits">
                {mm}:{ss}
              </Text>
              <Muted style={{ fontSize: 11 }}>
                {overtime ? 'Past full time' : `of ${match.duration_minutes}:00`}
              </Muted>
            </View>
            {canEdit && (
              <View style={{ flexDirection: 'row', gap: 8 }}>
                {!timerIsRunning && !match.timer_started_at && (
                  <TouchableOpacity testID="timer-start-btn" onPress={() => timerAction('start')} style={[styles.timerBtn, styles.timerBtnStart]} activeOpacity={0.85}>
                    <Ionicons name="play" size={18} color="#fff" />
                    <Text style={styles.timerBtnText}>START</Text>
                  </TouchableOpacity>
                )}
                {timerIsRunning && (
                  <TouchableOpacity testID="timer-stop-btn" onPress={() => timerAction('stop')} style={[styles.timerBtn, styles.timerBtnStop]} activeOpacity={0.85}>
                    <Ionicons name="stop" size={18} color="#fff" />
                    <Text style={styles.timerBtnText}>STOP</Text>
                  </TouchableOpacity>
                )}
                {match.timer_started_at && !timerIsRunning && (
                  <TouchableOpacity testID="timer-reset-btn" onPress={() => timerAction('reset')} style={[styles.timerBtn, styles.timerBtnReset]} activeOpacity={0.85}>
                    <Ionicons name="refresh" size={18} color={colors.textPrimary} />
                  </TouchableOpacity>
                )}
              </View>
            )}
          </View>
        )}

        {/* LIVE SCORE — quick +/- score panel for editors before the match is finalised */}
        {canEdit && match.status !== 'played' && match.lineup && (
          <View style={styles.liveScoreCard} testID="live-score-panel">
            <View style={styles.liveScoreHeader}>
              <View style={[styles.livePill, match.status === 'in_progress' ? styles.livePillOn : styles.livePillIdle]}>
                <View style={[styles.liveDot, match.status === 'in_progress' && styles.liveDotOn]} />
                <Text style={styles.livePillText}>{match.status === 'in_progress' ? 'LIVE' : 'SCORE'}</Text>
              </View>
              {match.tournament_id && (
                <Muted style={{ fontSize: 11 }}>Tournament fixture · standings update on every tap</Muted>
              )}
            </View>
            <View style={styles.liveScoreRow}>
              <View style={styles.liveTeam}>
                <Text style={styles.liveTeamLabel} numberOfLines={1}>
                  {match.tournament_home || 'TEAM RED'}
                </Text>
                <View style={styles.liveControls}>
                  <TouchableOpacity
                    testID="live-score-a-minus"
                    onPress={() => bumpLive('a', -1)}
                    disabled={liveBusy || liveA <= 0}
                    style={[styles.liveBtn, (liveBusy || liveA <= 0) && { opacity: 0.4 }]}
                    activeOpacity={0.7}
                  >
                    <Ionicons name="remove" size={20} color={colors.textPrimary} />
                  </TouchableOpacity>
                  <Text style={styles.liveScore} testID="live-score-a">{liveA}</Text>
                  <TouchableOpacity
                    testID="live-score-a-plus"
                    onPress={() => bumpLive('a', 1)}
                    disabled={liveBusy}
                    style={[styles.liveBtn, styles.liveBtnPlus, liveBusy && { opacity: 0.4 }]}
                    activeOpacity={0.7}
                  >
                    <Ionicons name="add" size={20} color="#fff" />
                  </TouchableOpacity>
                </View>
              </View>
              <Text style={styles.liveSep}>:</Text>
              <View style={styles.liveTeam}>
                <Text style={styles.liveTeamLabel} numberOfLines={1}>
                  {match.tournament_away || 'TEAM BLACK'}
                </Text>
                <View style={styles.liveControls}>
                  <TouchableOpacity
                    testID="live-score-b-minus"
                    onPress={() => bumpLive('b', -1)}
                    disabled={liveBusy || liveB <= 0}
                    style={[styles.liveBtn, (liveBusy || liveB <= 0) && { opacity: 0.4 }]}
                    activeOpacity={0.7}
                  >
                    <Ionicons name="remove" size={20} color={colors.textPrimary} />
                  </TouchableOpacity>
                  <Text style={styles.liveScore} testID="live-score-b">{liveB}</Text>
                  <TouchableOpacity
                    testID="live-score-b-plus"
                    onPress={() => bumpLive('b', 1)}
                    disabled={liveBusy}
                    style={[styles.liveBtn, styles.liveBtnPlus, liveBusy && { opacity: 0.4 }]}
                    activeOpacity={0.7}
                  >
                    <Ionicons name="add" size={20} color="#fff" />
                  </TouchableOpacity>
                </View>
              </View>
            </View>
            <Muted style={{ fontSize: 11, marginTop: 6, textAlign: 'center' }}>
              Tip: tap +/- to track goals live. When the match ends, open the result modal to assign scorers/assists.
            </Muted>
          </View>
        )}

        {match.status !== 'played' && (
          <>
            <Overline style={{ marginTop: spacing.lg, marginBottom: spacing.sm }}>Cast your vote</Overline>
            <View style={styles.voteRow}>
              {([
                { v: 'yes' as const, label: 'YES', color: colors.success, icon: 'checkmark-circle' as const, count: yesVoters.length },
                { v: 'reserve' as const, label: 'RESERVE', color: colors.warning, icon: 'time' as const, count: resVoters.length },
                { v: 'no' as const, label: 'NO', color: colors.danger, icon: 'close-circle' as const, count: noVoters.length },
              ]).map((vc) => (
                <TouchableOpacity
                  key={vc.v}
                  testID={`detail-vote-${vc.v}-btn`}
                  disabled={busy}
                  onPress={() => vote(vc.v)}
                  activeOpacity={0.85}
                  style={[
                    styles.voteCard,
                    { borderColor: vc.color, backgroundColor: `${vc.color}1a` },
                    myVote === vc.v && { backgroundColor: `${vc.color}4a`, borderWidth: 3 },
                  ]}
                >
                  <Ionicons name={vc.icon} size={36} color={vc.color} />
                  <Text style={[styles.voteCount, { color: vc.color, fontWeight: '900', fontSize: 14 }]}>{vc.count}</Text>
                </TouchableOpacity>
              ))}
            </View>
          </>
        )}

        <View style={styles.lineupHeader}>
          <Overline>Lineup</Overline>
          {canEdit && match.lineup && (
            <TouchableOpacity testID="edit-lineup-btn" onPress={openLineupEdit} style={styles.editLineupBtn} activeOpacity={0.85}>
              <Ionicons name="create-outline" size={14} color={colors.primary} />
              <Text style={styles.editLineupText}>EDIT</Text>
            </TouchableOpacity>
          )}
        </View>

        <View style={styles.pitch}>
          <View style={styles.midLine} />
          <View style={styles.midCircle} />
          <View style={[styles.box, styles.boxTop]} />
          <View style={[styles.box, styles.boxBottom]} />
          {coords.map((c, i) => (
            <PlayerMarker
              key={`b-${i}`}
              player={teamB[i]}
              x={c.x}
              y={c.y}
              flip
              color={TEAM_COLORS.b.primary}
              textColor={TEAM_COLORS.b.text}
              onPress={canEdit ? () => onPitchTap('b', i) : undefined}
              selected={pitchSel?.team === 'b' && pitchSel.index === i}
            />
          ))}
          {coords.map((c, i) => (
            <PlayerMarker
              key={`a-${i}`}
              player={teamA[i]}
              x={c.x}
              y={c.y}
              color={TEAM_COLORS.a.primary}
              textColor={TEAM_COLORS.a.text}
              onPress={canEdit ? () => onPitchTap('a', i) : undefined}
              selected={pitchSel?.team === 'a' && pitchSel.index === i}
            />
          ))}
        </View>
        {canEdit && match.lineup && (
          <View style={styles.swapHint}>
            {swapBusy ? (
              <ActivityIndicator size="small" color={colors.primary} />
            ) : (
              <Ionicons name={pitchSel ? 'swap-horizontal' : 'finger-print-outline'} size={14} color={colors.textMuted} />
            )}
            <Text style={styles.swapHintText}>
              {swapBusy
                ? 'Saving lineup…'
                : pitchSel
                ? `Swap selected — tap another player (any team) to swap, or tap again to cancel`
                : 'Tap two players to swap their pitch positions'}
            </Text>
            {pitchSel && !swapBusy && (
              <TouchableOpacity onPress={() => setPitchSel(null)} hitSlop={8}>
                <Ionicons name="close" size={16} color={colors.textMuted} />
              </TouchableOpacity>
            )}
          </View>
        )}

        <View style={styles.lineupMeta}>
          <Text style={styles.teamLabel}><Text style={{ color: TEAM_COLORS.a.primary }}>■ </Text>TEAM RED ({teamA.length})</Text>
          <Text style={styles.teamLabel}><Text style={{ color: '#71717A' }}>■ </Text>TEAM BLACK ({teamB.length})</Text>
        </View>

        {threeTeam && (
          <View style={styles.thirdTeamCard}>
            <View style={styles.thirdTeamHeader}>
              <View style={styles.thirdTeamDot} />
              <Text style={styles.teamLabel}>TEAM WHITE ({teamC.length})</Text>
              <Muted style={{ marginLeft: 'auto', fontSize: 11 }}>Rotates in</Muted>
            </View>
            {teamC.length === 0 ? <Muted style={{ fontSize: 12 }}>—</Muted> : (
              <View style={styles.thirdTeamList}>
                {teamC.map((p) => (
                  <View key={p.user_id} style={styles.thirdTeamPlayer}>
                    <Text style={styles.thirdTeamNumber}>{p.shirt_number ?? '·'}</Text>
                    <Text style={styles.thirdTeamName} numberOfLines={1}>{p.name}</Text>
                  </View>
                ))}
              </View>
            )}
          </View>
        )}

        {canEdit && match.status === 'voting' && (
          <TouchableOpacity testID="generate-lineup-btn" disabled={busy || yesVoters.length === 0} onPress={generateLineup}
            style={[styles.primaryBtn, (busy || yesVoters.length === 0) && { opacity: 0.5 }]} activeOpacity={0.85}>
            <Text style={styles.primaryBtnText}>GENERATE LINEUP</Text>
          </TouchableOpacity>
        )}

        <Overline style={{ marginTop: spacing.lg, marginBottom: spacing.sm }}>Availability ({match.votes.length})</Overline>
        {[
          { label: 'AVAILABLE', list: yesVoters, color: colors.success },
          { label: 'RESERVE', list: resVoters, color: colors.warning },
          { label: 'UNAVAILABLE', list: noVoters, color: colors.danger },
        ].map((g) => (
          <View key={g.label} style={styles.group}>
            <Text style={[styles.groupLabel, { color: g.color }]}>{g.label} · {g.list.length}</Text>
            {g.list.length === 0 ? <Muted style={{ marginBottom: spacing.sm }}>—</Muted> :
              g.list.map((v) => (
                <View key={v.user_id} style={styles.voterRow}>
                  <Avatar uri={v.profile_picture} size={36} name={v.name} shirt={v.shirt_number || undefined} />
                  <View style={{ flex: 1, flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                    <Text style={styles.voterName} numberOfLines={1}>{v.name}</Text>
                    {(() => {
                      const posList = (v.preferred_positions && v.preferred_positions.length > 0)
                        ? v.preferred_positions
                        : (v.preferred_position ? [v.preferred_position] : []);
                      if (posList.length === 0) return null;
                      return <View style={styles.posBadge}><Text style={styles.posBadgeText}>{posList.slice(0, 2).join('/')}</Text></View>;
                    })()}
                  </View>
                  <Text style={styles.voterRating}>{v.rating}</Text>
                </View>
              ))
            }
          </View>
        ))}

        {canEdit && (
          <TouchableOpacity testID="record-result-btn" onPress={openResult} style={styles.secondaryBtn} activeOpacity={0.85}>
            <Ionicons name="stats-chart-outline" size={18} color={colors.textPrimary} />
            <Text style={styles.secondaryBtnText}>{match.result ? 'EDIT RESULT' : 'RECORD RESULT'}</Text>
          </TouchableOpacity>
        )}

        {/* ---------- Man of the Match ---------- */}
        {motm && motm.open && (
          <View style={styles.motmCard}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <Ionicons name="trophy" size={20} color="#FFD700" />
              <Text style={styles.motmTitle}>MAN OF THE MATCH</Text>
              <Text style={styles.motmTotal}>{motm.total} vote{motm.total === 1 ? '' : 's'}</Text>
            </View>
            {!motm.can_vote && (
              <Muted style={{ fontSize: 12, marginBottom: 8 }}>
                Only players who said YES can vote.
              </Muted>
            )}
            {motm.candidates.length === 0 ? (
              <Muted>No candidates yet (no players in the lineup).</Muted>
            ) : (
              motm.candidates.map((cid) => {
                const player =
                  [...(match.lineup?.team_a || []), ...(match.lineup?.team_b || []), ...(match.lineup?.team_c || [])]
                    .find((p: any) => p.user_id === cid);
                if (!player) return null;
                const count = motm.votes[cid] || 0;
                const myChoice = motm.my_choice === cid;
                const isWinner = motm.winner_id === cid && motm.total > 0;
                const isMe = user?.id === cid;
                const pct = motm.total > 0 ? Math.round((count / motm.total) * 100) : 0;
                return (
                  <TouchableOpacity
                    key={cid}
                    testID={`motm-vote-${cid}`}
                    disabled={!motm.can_vote || isMe || motmBusy}
                    onPress={() => castMotm(cid)}
                    activeOpacity={0.85}
                    style={[
                      styles.motmRow,
                      myChoice && { borderColor: colors.primary, backgroundColor: '#1f1105' },
                      isWinner && { borderColor: '#FFD700' },
                      (isMe || !motm.can_vote) && { opacity: 0.65 },
                    ]}
                  >
                    <Avatar uri={player.profile_picture} size={32} name={player.name} shirt={player.shirt_number || undefined} />
                    <View style={{ flex: 1 }}>
                      <Text style={styles.motmName} numberOfLines={1}>
                        {player.name}{isMe ? ' (you)' : ''}
                      </Text>
                      {motm.total > 0 && (
                        <View style={styles.motmBarBg}>
                          <View style={[styles.motmBarFill, { width: `${pct}%`, backgroundColor: isWinner ? '#FFD700' : colors.primary }]} />
                        </View>
                      )}
                    </View>
                    {isWinner && <Ionicons name="trophy" size={18} color="#FFD700" />}
                    <Text style={[styles.motmCount, isWinner && { color: '#FFD700' }]}>
                      {count}
                    </Text>
                    {myChoice && <Ionicons name="checkmark-circle" size={18} color={colors.primary} />}
                  </TouchableOpacity>
                );
              })
            )}
          </View>
        )}

        {/* ----------- Match Chat ----------- */}
        <View style={styles.chatSection}>
          <View style={styles.chatHeader}>
            <Ionicons name="chatbubbles" size={18} color={colors.primary} />
            <Text style={styles.chatTitle}>MATCH CHAT</Text>
            <Text style={styles.chatCount}>{comments.length}</Text>
          </View>

          {comments.length === 0 ? (
            <Muted style={{ textAlign: 'center', paddingVertical: spacing.md }}>
              No messages yet. Be the first to post!
            </Muted>
          ) : (
            comments.map((c) => {
              const mine = user?.id === c.user_id;
              const canDelete = mine || canEdit;
              const when = (() => {
                try {
                  const d = new Date(c.created_at);
                  return d.toLocaleString(undefined, {
                    hour: '2-digit',
                    minute: '2-digit',
                    month: 'short',
                    day: 'numeric',
                  });
                } catch { return ''; }
              })();
              return (
                <View
                  key={c.id}
                  testID={`comment-${c.id}`}
                  style={[styles.chatBubble, mine && styles.chatBubbleMine]}
                >
                  <Avatar uri={c.profile_picture} size={32} name={c.name || '?'} />
                  <View style={{ flex: 1, marginLeft: 10 }}>
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                      <Text style={styles.chatName} numberOfLines={1}>
                        {c.name || 'Unknown'}{mine ? ' (you)' : ''}
                      </Text>
                      <Text style={styles.chatTime}>{when}</Text>
                    </View>
                    <Text style={styles.chatText}>{c.text}</Text>
                  </View>
                  {canDelete && (
                    <TouchableOpacity
                      testID={`comment-delete-${c.id}`}
                      onPress={() => deleteComment(c.id)}
                      hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                      style={{ padding: 4 }}
                    >
                      <Ionicons name="trash-outline" size={16} color={colors.textMuted} />
                    </TouchableOpacity>
                  )}
                </View>
              );
            })
          )}

          {user && (
            <View style={styles.chatInputRow}>
              <TextInput
                testID="chat-input"
                value={commentDraft}
                onChangeText={setCommentDraft}
                placeholder="Write a message…"
                placeholderTextColor={colors.textMuted}
                multiline
                maxLength={500}
                style={styles.chatInput}
              />
              <TouchableOpacity
                testID="chat-send-btn"
                onPress={postComment}
                disabled={postingComment || !commentDraft.trim()}
                style={[
                  styles.chatSendBtn,
                  (postingComment || !commentDraft.trim()) && { opacity: 0.5 },
                ]}
                activeOpacity={0.85}
              >
                {postingComment
                  ? <ActivityIndicator color="#fff" size="small" />
                  : <Ionicons name="send" size={18} color="#fff" />}
              </TouchableOpacity>
            </View>
          )}
        </View>
      </ScrollView>

      {/* Result modal — with steppers */}
      <Modal visible={resultOpen} transparent animationType="slide" onRequestClose={() => setResultOpen(false)}>
        <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={styles.modalBg}>
          <View style={styles.modalCard}>
            <ScrollView showsVerticalScrollIndicator={false}>
              <View style={styles.modalHeader}>
                <Title style={{ fontSize: 20 }}>Match Result</Title>
                <TouchableOpacity testID="close-result-modal" onPress={() => setResultOpen(false)} hitSlop={12}>
                  <Ionicons name="close" size={24} color={colors.textSecondary} />
                </TouchableOpacity>
              </View>

              <Text style={styles.label}>SCORES</Text>
              <View style={styles.scoresRow}>
                <View style={{ flex: 1, alignItems: 'center' }}>
                  <Text style={[styles.teamSmall, { color: TEAM_COLORS.a.primary }]}>RED</Text>
                  <Stepper value={scoreA} onChange={setScoreA} testID="score-a" />
                </View>
                <View style={{ flex: 1, alignItems: 'center' }}>
                  <Text style={[styles.teamSmall, { color: '#FAFAFA' }]}>BLACK</Text>
                  <Stepper value={scoreB} onChange={setScoreB} testID="score-b" />
                </View>
                {threeTeam && (
                  <View style={{ flex: 1, alignItems: 'center' }}>
                    <Text style={[styles.teamSmall, { color: '#fff' }]}>WHITE</Text>
                    <Stepper value={scoreC} onChange={setScoreC} testID="score-c" />
                  </View>
                )}
              </View>

              {match.match_type === 'league' && !threeTeam && (
                <Muted style={{ fontSize: 11, marginTop: 4 }}>League points: winner +3, draw +1, loser +0</Muted>
              )}

              <Text style={[styles.label, { marginTop: spacing.md }]}>Tap + to add goals & assists (team score auto-updates)</Text>
              {allPlayersForResult.length === 0 ? (
                <Muted>No lineup yet. A lineup will be auto-generated from yes voters when you save.</Muted>
              ) : (
                allPlayersForResult.map((p) => {
                  const stat = playerStats[p.user_id] || { goals: 0, assists: 0 };
                  // Determine which team this player is in for auto-score bump
                  const playerTeam: 'a' | 'b' | 'c' | null = teamA.some((x: any) => x.user_id === p.user_id)
                    ? 'a'
                    : teamB.some((x: any) => x.user_id === p.user_id)
                    ? 'b'
                    : teamC.some((x: any) => x.user_id === p.user_id)
                    ? 'c'
                    : null;
                  const teamColour = playerTeam === 'a'
                    ? colors.danger
                    : playerTeam === 'b'
                    ? colors.textPrimary
                    : playerTeam === 'c'
                    ? colors.warning
                    : colors.textMuted;
                  const teamLabel = playerTeam === 'a' ? 'A' : playerTeam === 'b' ? 'B' : playerTeam === 'c' ? 'C' : '?';
                  return (
                    <View key={p.user_id} style={styles.statRow}>
                      <Avatar uri={p.profile_picture} size={36} name={p.name} shirt={p.shirt_number || undefined} />
                      <View style={{ flex: 1, flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                        <View style={{
                          width: 22, height: 22, borderRadius: 11, alignItems: 'center', justifyContent: 'center',
                          backgroundColor: teamColour,
                        }}>
                          <Text style={{ color: playerTeam === 'b' ? '#000' : '#fff', fontSize: 11, fontWeight: '900' }}>{teamLabel}</Text>
                        </View>
                        <Text style={styles.statName} numberOfLines={1}>{p.name}</Text>
                      </View>
                      <View style={{ alignItems: 'center', gap: 2 }}>
                        <Text style={styles.statLabel}>GOAL</Text>
                        <Stepper
                          testID={`goals-${p.user_id}`}
                          value={stat.goals}
                          onChange={(v) => {
                            const oldGoals = playerStats[p.user_id]?.goals || 0;
                            const delta = v - oldGoals;
                            setPlayerStats((s) => ({
                              ...s,
                              [p.user_id]: { goals: v, assists: s[p.user_id]?.assists || 0 },
                            }));
                            // Auto-update the corresponding team's score by the delta
                            if (delta !== 0 && playerTeam) {
                              if (playerTeam === 'a') setScoreA((cur) => Math.max(0, cur + delta));
                              else if (playerTeam === 'b') setScoreB((cur) => Math.max(0, cur + delta));
                              else if (playerTeam === 'c') setScoreC((cur) => Math.max(0, cur + delta));
                            }
                          }}
                        />
                      </View>
                      <View style={{ alignItems: 'center', gap: 2 }}>
                        <Text style={styles.statLabel}>ASSIST</Text>
                        <Stepper
                          testID={`assists-${p.user_id}`}
                          value={stat.assists}
                          onChange={(v) => setPlayerStats((s) => ({ ...s, [p.user_id]: { goals: s[p.user_id]?.goals || 0, assists: v } }))}
                        />
                      </View>
                    </View>
                  );
                })
              )}

              <TouchableOpacity testID="save-result-btn" disabled={busy} onPress={saveResult}
                style={[styles.primaryBtn, busy && { opacity: 0.5 }]} activeOpacity={0.85}>
                {busy ? <ActivityIndicator color="#fff" /> : <Text style={styles.primaryBtnText}>SAVE RESULT</Text>}
              </TouchableOpacity>
            </ScrollView>
          </View>
        </KeyboardAvoidingView>
      </Modal>

      {/* Lineup edit modal */}
      <Modal visible={lineupEditOpen} transparent animationType="slide" onRequestClose={() => setLineupEditOpen(false)}>
        <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={styles.modalBg}>
          <View style={styles.modalCard}>
            <ScrollView showsVerticalScrollIndicator={false}>
              <View style={styles.modalHeader}>
                <Title style={{ fontSize: 20 }}>Edit Lineup</Title>
                <TouchableOpacity testID="close-lineup-modal" onPress={() => setLineupEditOpen(false)} hitSlop={12}>
                  <Ionicons name="close" size={24} color={colors.textSecondary} />
                </TouchableOpacity>
              </View>

              <View style={styles.addBtnRow}>
                <TouchableOpacity
                  testID="add-registered-btn"
                  onPress={() => setAddPickerOpen((o) => !o)}
                  style={styles.addBtn}
                  activeOpacity={0.85}
                >
                  <Ionicons name="person-add-outline" size={14} color={colors.primary} />
                  <Text style={styles.addBtnText}>+ PLAYER</Text>
                </TouchableOpacity>
              </View>

              {addPickerOpen && (
                <View style={styles.pickerCard}>
                  <Text style={styles.label}>PICK A REGISTERED USER</Text>
                  {(() => {
                    const inLineup = new Set(Object.keys(draftBuckets));
                    const available = allUsers.filter((u) => !inLineup.has(u.id));
                    if (available.length === 0) {
                      return <Muted style={{ fontSize: 12 }}>Everyone is already in the lineup.</Muted>;
                    }
                    return available.map((u) => (
                      <TouchableOpacity
                        key={u.id}
                        testID={`pick-user-${u.id}`}
                        onPress={() => addRegisteredToLineup(u)}
                        style={styles.pickerRow}
                        activeOpacity={0.8}
                      >
                        <Avatar uri={u.profile_picture} size={30} name={u.name} shirt={u.shirt_number || undefined} />
                        <Text style={styles.pickerName} numberOfLines={1}>{u.name}</Text>
                        {(() => {
                          const posList = (u.preferred_positions && u.preferred_positions.length > 0)
                            ? u.preferred_positions
                            : (u.preferred_position ? [u.preferred_position] : []);
                          if (posList.length === 0) return null;
                          return (
                            <View style={styles.posBadge}>
                              <Text style={styles.posBadgeText}>{posList.slice(0, 2).join('/')}</Text>
                            </View>
                          );
                        })()}
                        <Ionicons name="add-circle" size={20} color={colors.primary} />
                      </TouchableOpacity>
                    ));
                  })()}
                </View>
              )}

              <View style={styles.guestCard}>
                <Text style={styles.label}>+ ADD GUEST (NON-USER)</Text>
                <View style={{ flexDirection: 'row', gap: 8 }}>
                  <TextInput
                    testID="guest-name-input"
                    value={guestName}
                    onChangeText={setGuestName}
                    placeholder="Guest name"
                    placeholderTextColor="#888"
                    underlineColorAndroid="transparent"
                    autoComplete="off"
                    autoCorrect={false}
                    importantForAutofill="no"
                    keyboardType="visible-password"
                    secureTextEntry={false}
                    spellCheck={false}
                    selectionColor="#FF4500"
                    style={{
                      flex: 1,
                      minWidth: 0,
                      backgroundColor: '#FFFFFF',
                      borderWidth: 1,
                      borderColor: colors.border,
                      borderRadius: radii.md,
                      paddingHorizontal: spacing.md,
                      height: 44,
                      color: '#000000',
                      fontSize: 16,
                    }}
                  />
                  <TextInput
                    testID="guest-shirt-input"
                    value={guestShirt}
                    onChangeText={(t) => setGuestShirt(t.replace(/[^0-9]/g, '').slice(0, 2))}
                    keyboardType="number-pad"
                    placeholder="#"
                    placeholderTextColor="#888"
                    underlineColorAndroid="transparent"
                    autoComplete="off"
                    autoCorrect={false}
                    importantForAutofill="no"
                    spellCheck={false}
                    selectionColor="#FF4500"
                    style={{
                      width: 56,
                      backgroundColor: '#FFFFFF',
                      borderWidth: 1,
                      borderColor: colors.border,
                      borderRadius: radii.md,
                      paddingHorizontal: 8,
                      height: 44,
                      color: '#000000',
                      fontSize: 16,
                      textAlign: 'center',
                    }}
                  />
                </View>
                <View style={{ marginTop: 10 }}>
                  <Text style={[styles.label, { marginBottom: 4 }]}>POSITION (optional)</Text>
                  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
                    {(['GK', 'CB', 'LB', 'RB', 'CDM', 'CM', 'CAM', 'LW', 'ST', 'RW', 'ANY'] as const).map((p) => {
                      const active = guestPosition === p;
                      return (
                        <TouchableOpacity
                          key={p}
                          testID={`guest-pos-${p}-btn`}
                          onPress={() => setGuestPosition(active ? null : p)}
                          activeOpacity={0.85}
                          style={{
                            paddingHorizontal: 10,
                            height: 30,
                            borderRadius: radii.sm,
                            borderWidth: 1,
                            borderColor: active ? colors.primary : colors.border,
                            backgroundColor: active ? colors.primary : 'transparent',
                            alignItems: 'center',
                            justifyContent: 'center',
                          }}
                        >
                          <Text style={{
                            color: active ? '#fff' : colors.textSecondary,
                            fontSize: 12,
                            fontWeight: '700',
                          }}>{p}</Text>
                        </TouchableOpacity>
                      );
                    })}
                  </View>
                </View>
                <TouchableOpacity
                  testID="add-guest-btn"
                  onPress={addGuestToLineup}
                  style={styles.guestAddBtnFull}
                  activeOpacity={0.85}
                >
                  <Ionicons name="add-circle" size={18} color="#fff" />
                  <Text style={styles.guestAddBtnFullText}>ADD GUEST PLAYER</Text>
                </TouchableOpacity>
              </View>

              <Muted style={{ marginTop: spacing.md, marginBottom: spacing.sm, fontSize: 12 }}>
                Tap a team pill to reassign. Red & Black max {match.team_size} each.
              </Muted>

              {(() => {
                const existing = match.lineup
                  ? [...match.lineup.team_a, ...match.lineup.team_b, ...match.lineup.team_c, ...match.lineup.reserves]
                  : [];
                const merged = [...existing, ...draftExtras];
                // Only keep those still in draftBuckets (removals respected)
                return merged.filter((p) => draftBuckets[p.user_id]);
              })().map((p) => {
                const current = draftBuckets[p.user_id] || 'reserves';
                const isGuest = (p as any).is_guest || p.user_id.startsWith('guest:');
                const teams: { key: Bucket; label: string; color: string; textColor?: string }[] = [
                  { key: 'team_a', label: 'RED', color: TEAM_COLORS.a.primary },
                  { key: 'team_b', label: 'BLACK', color: TEAM_COLORS.b.primary },
                  { key: 'team_c', label: 'WHITE', color: TEAM_COLORS.c.primary, textColor: '#111' },
                  { key: 'reserves', label: 'RES', color: colors.surfaceAccent },
                ];
                return (
                  <View key={p.user_id} style={styles.editRow}>
                    <Avatar uri={p.profile_picture} size={34} name={p.name} shirt={p.shirt_number || undefined} />
                    <View style={{ flex: 1, flexDirection: 'row', alignItems: 'center', gap: 4 }}>
                      <Text style={styles.editName} numberOfLines={1}>{p.name}</Text>
                      {isGuest && (
                        <View style={styles.guestBadge}>
                          <Text style={styles.guestBadgeText}>GUEST</Text>
                        </View>
                      )}
                    </View>
                    <View style={{ flexDirection: 'row', gap: 4 }}>
                      {teams.map((t) => {
                        const selected = current === t.key;
                        return (
                          <TouchableOpacity
                            key={t.key}
                            testID={`assign-${p.user_id}-${t.key}`}
                            onPress={() => setDraftBuckets((b) => ({ ...b, [p.user_id]: t.key }))}
                            style={[styles.pill, selected && { backgroundColor: t.color, borderColor: t.color }]}
                            activeOpacity={0.8}
                          >
                            <Text style={[styles.pillText, selected && { color: t.textColor || '#fff' }]}>{t.label}</Text>
                          </TouchableOpacity>
                        );
                      })}
                      <TouchableOpacity
                        testID={`remove-${p.user_id}`}
                        onPress={() => removeFromLineup(p.user_id)}
                        style={styles.removeBtn}
                        hitSlop={6}
                      >
                        <Ionicons name="close" size={14} color={colors.danger} />
                      </TouchableOpacity>
                    </View>
                  </View>
                );
              })}

              <TouchableOpacity testID="save-lineup-btn" disabled={busy} onPress={saveLineup}
                style={[styles.primaryBtn, busy && { opacity: 0.5 }]} activeOpacity={0.85}>
                {busy ? <ActivityIndicator color="#fff" /> : <Text style={styles.primaryBtnText}>SAVE LINEUP</Text>}
              </TouchableOpacity>
            </ScrollView>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  scroll: { paddingHorizontal: spacing.lg, paddingBottom: spacing.xxl, paddingTop: spacing.md },
  headerRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: spacing.sm },
  iconBtn: { width: 38, height: 38, alignItems: 'center', justifyContent: 'center', borderRadius: radii.md, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border },
  chipsRow: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.sm, flexWrap: 'wrap' },
  chip: { backgroundColor: colors.surfaceAccent, paddingHorizontal: spacing.md, paddingVertical: 6, borderRadius: radii.sm, borderWidth: 1, borderColor: colors.border },
  chipText: { color: colors.textPrimary, fontWeight: '800', letterSpacing: 0.5, fontSize: 12 },
  scoreChip: { backgroundColor: colors.primary, borderColor: colors.primary },
  scoreChipText: { color: '#fff', fontWeight: '900', fontSize: 13 },
  timerCard: {
    marginTop: spacing.lg,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.lg,
    padding: spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
  },
  timerDigits: {
    color: colors.textPrimary,
    fontSize: 40,
    fontWeight: '900',
    letterSpacing: 2,
    lineHeight: 44,
    marginTop: 4,
    fontVariant: ['tabular-nums'],
  },
  timerBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 14,
    height: 40,
    borderRadius: radii.md,
  },
  timerBtnStart: { backgroundColor: colors.success },
  timerBtnStop: { backgroundColor: colors.danger },
  timerBtnReset: { backgroundColor: colors.surfaceAccent, borderWidth: 1, borderColor: colors.border, width: 40, justifyContent: 'center' },
  timerBtnText: { color: '#fff', fontWeight: '900', letterSpacing: 1, fontSize: 12 },
  voteRow: { flexDirection: 'row', gap: spacing.sm },
  voteCard: { flex: 1, aspectRatio: 1, borderWidth: 2, borderRadius: radii.md, alignItems: 'center', justifyContent: 'center', gap: 4, paddingVertical: spacing.sm },
  voteLabel: { fontSize: 13, fontWeight: '900', letterSpacing: 1 },
  voteCount: { color: colors.textPrimary, fontSize: 18, fontWeight: '800' },
  lineupHeader: { marginTop: spacing.lg, marginBottom: spacing.sm, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  editLineupBtn: { flexDirection: 'row', alignItems: 'center', gap: 4, paddingHorizontal: 10, paddingVertical: 6, borderRadius: radii.sm, borderWidth: 1, borderColor: colors.primary, backgroundColor: colors.surface },
  editLineupText: { color: colors.primary, fontWeight: '900', fontSize: 11, letterSpacing: 1 },
  pitch: { width: '100%', aspectRatio: 0.66, backgroundColor: '#14532d', borderRadius: radii.lg, borderWidth: 2, borderColor: '#166534', overflow: 'hidden', position: 'relative' },
  swapHint: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  swapHintText: {
    flex: 1,
    color: colors.textSecondary,
    fontSize: 12,
    fontWeight: '600',
  },
  motmCard: {
    marginTop: spacing.lg,
    padding: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: '#FFD70044',
  },
  motmTitle: {
    color: colors.textPrimary,
    fontWeight: '900',
    letterSpacing: 1.2,
    fontSize: 13,
    flex: 1,
  },
  motmTotal: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: '700',
  },
  motmRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingHorizontal: spacing.sm,
    paddingVertical: 8,
    backgroundColor: colors.background,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: 6,
  },
  motmName: {
    color: colors.textPrimary,
    fontSize: 13,
    fontWeight: '700',
  },
  motmCount: {
    color: colors.textPrimary,
    fontSize: 14,
    fontWeight: '900',
    minWidth: 24,
    textAlign: 'right',
  },
  motmBarBg: {
    height: 4,
    backgroundColor: colors.border,
    borderRadius: 2,
    marginTop: 4,
    overflow: 'hidden',
  },
  motmBarFill: {
    height: 4,
  },
  midLine: { position: 'absolute', top: '50%', left: 0, right: 0, height: 2, backgroundColor: 'rgba(255,255,255,0.35)' },
  midCircle: { position: 'absolute', top: '50%', left: '50%', width: 90, height: 90, marginLeft: -45, marginTop: -45, borderRadius: 45, borderWidth: 2, borderColor: 'rgba(255,255,255,0.35)' },
  box: { position: 'absolute', width: '60%', left: '20%', height: '14%', borderWidth: 2, borderColor: 'rgba(255,255,255,0.35)' },
  boxTop: { top: 0, borderTopWidth: 0 },
  boxBottom: { bottom: 0, borderBottomWidth: 0 },
  markerWrap: { position: 'absolute', width: 44, height: 44, marginLeft: -22, marginTop: -22, alignItems: 'center', justifyContent: 'center' },
  marker: { width: 44, height: 44, borderRadius: 22, borderWidth: 3, alignItems: 'center', justifyContent: 'center' },
  markerEmpty: { position: 'absolute', width: 32, height: 32, borderRadius: 16, marginLeft: -16, marginTop: -16, borderStyle: 'dashed', backgroundColor: 'rgba(255,255,255,0.07)', borderWidth: 2, alignItems: 'center', justifyContent: 'center' },
  markerEmptyText: { color: 'rgba(255,255,255,0.6)', fontWeight: '900', fontSize: 14 },
  markerNumber: { fontWeight: '900', fontSize: 15 },
  markerName: { position: 'absolute', width: 80, marginLeft: -18, color: '#fff', fontSize: 10, fontWeight: '800', textAlign: 'center', textShadowColor: 'rgba(0,0,0,0.85)', textShadowOffset: { width: 0, height: 1 }, textShadowRadius: 2 },
  markerNameAbove: { top: -14 },
  markerNameBelow: { top: 46 },
  lineupMeta: { flexDirection: 'row', justifyContent: 'space-between', marginTop: spacing.sm },
  teamLabel: { color: colors.textSecondary, fontSize: 11, fontWeight: '900', letterSpacing: 1.2 },
  thirdTeamCard: { marginTop: spacing.md, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.borderLight, borderRadius: radii.md, padding: spacing.md },
  thirdTeamHeader: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 6 },
  thirdTeamDot: { width: 10, height: 10, borderRadius: 5, backgroundColor: TEAM_COLORS.c.primary, borderWidth: 1, borderColor: colors.borderLight },
  thirdTeamList: { gap: 4 },
  thirdTeamPlayer: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  thirdTeamNumber: { width: 22, color: TEAM_COLORS.c.primary, fontWeight: '900', fontSize: 12, textAlign: 'center' },
  thirdTeamName: { color: colors.textPrimary, fontWeight: '700', fontSize: 13, flex: 1 },
  group: { marginBottom: spacing.md },
  groupLabel: { fontSize: 11, fontWeight: '900', letterSpacing: 1.5, marginBottom: spacing.sm },
  voterRow: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radii.md, padding: spacing.sm, marginBottom: 6, gap: spacing.sm },
  voterName: { color: colors.textPrimary, fontWeight: '700', flexShrink: 1 },
  posBadge: { paddingHorizontal: 6, paddingVertical: 1, borderRadius: 4, backgroundColor: colors.surfaceAccent, borderWidth: 1, borderColor: colors.borderLight },
  posBadgeText: { color: colors.textSecondary, fontSize: 9, fontWeight: '900', letterSpacing: 1 },
  voterRating: { color: colors.primary, fontWeight: '900' },
  primaryBtn: { marginTop: spacing.md, backgroundColor: colors.primary, height: 50, alignItems: 'center', justifyContent: 'center', borderRadius: radii.md, borderBottomWidth: 4, borderBottomColor: colors.primaryDark },
  primaryBtnText: { color: '#fff', fontSize: 15, fontWeight: '900', letterSpacing: 1 },
  secondaryBtn: { marginTop: spacing.md, height: 50, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, borderRadius: radii.md, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border },
  secondaryBtnText: { color: colors.textPrimary, fontSize: 14, fontWeight: '900', letterSpacing: 1 },
  modalBg: { flex: 1, backgroundColor: 'rgba(0,0,0,0.7)', justifyContent: 'flex-end' },
  modalCard: { backgroundColor: colors.surface, borderTopLeftRadius: radii.xl, borderTopRightRadius: radii.xl, padding: spacing.lg, maxHeight: '88%' },
  modalHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: spacing.md },
  label: { color: colors.textSecondary, fontSize: 11, fontWeight: '800', letterSpacing: 2, marginBottom: spacing.sm },
  scoresRow: { flexDirection: 'row', gap: spacing.md },
  teamSmall: { fontSize: 10, fontWeight: '900', letterSpacing: 1.5, textAlign: 'center', marginBottom: 6 },
  statRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, backgroundColor: colors.background, borderWidth: 1, borderColor: colors.border, borderRadius: radii.md, padding: spacing.sm, marginBottom: 6 },
  statName: { flex: 1, color: colors.textPrimary, fontWeight: '700', fontSize: 13 },
  statLabel: { color: colors.textMuted, fontSize: 9, fontWeight: '900', letterSpacing: 1 },
  stepper: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  stepperBtn: { width: 32, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.surfaceAccent, borderWidth: 1, borderColor: colors.border },
  stepperBtnPrimary: { backgroundColor: colors.primary, borderColor: colors.primary },
  stepperValue: { minWidth: 20, textAlign: 'center', color: colors.textPrimary, fontWeight: '900', fontSize: 18 },
  editRow: { flexDirection: 'row', alignItems: 'center', gap: 8, padding: 8, borderRadius: radii.sm, backgroundColor: colors.background, borderWidth: 1, borderColor: colors.border, marginBottom: 4 },
  editName: { flex: 1, color: colors.textPrimary, fontWeight: '700', fontSize: 13 },
  pill: { paddingHorizontal: 8, height: 28, minWidth: 44, alignItems: 'center', justifyContent: 'center', borderRadius: 14, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surfaceAccent },
  pillText: { color: colors.textSecondary, fontWeight: '900', fontSize: 10, letterSpacing: 1 },
  addBtnRow: { flexDirection: 'row', gap: 8, marginBottom: spacing.sm },
  addBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 10,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.primary,
    backgroundColor: colors.surface,
  },
  addBtnText: { color: colors.primary, fontWeight: '900', fontSize: 11, letterSpacing: 1 },
  pickerCard: {
    marginBottom: spacing.sm,
    padding: spacing.sm,
    backgroundColor: colors.background,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    maxHeight: 240,
  },
  pickerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 6,
    paddingHorizontal: 4,
  },
  pickerName: { flex: 1, color: colors.textPrimary, fontWeight: '700', fontSize: 13 },
  guestCard: {
    marginBottom: spacing.sm,
    padding: spacing.sm,
    backgroundColor: colors.background,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  guestAddBtn: {
    width: 48,
    height: 48,
    borderRadius: radii.md,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primary,
  },
  guestAddBtnFull: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    height: 44,
    borderRadius: radii.md,
    backgroundColor: colors.primary,
    marginTop: 12,
  },
  guestAddBtnFullText: {
    color: '#fff',
    fontSize: 13,
    fontWeight: '900',
    letterSpacing: 1,
  },
  guestBadge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    backgroundColor: colors.warning,
  },
  guestBadgeText: { color: '#fff', fontSize: 9, fontWeight: '900', letterSpacing: 1 },
  removeBtn: {
    width: 24,
    height: 28,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: 4,
    marginLeft: 2,
  },
  input: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.md,
    paddingHorizontal: spacing.md,
    height: 48,
    color: colors.textPrimary,
    fontSize: 16,
  },

  // Match Chat
  chatSection: {
    marginTop: spacing.lg,
    padding: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chatHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: spacing.sm,
  },
  chatTitle: {
    color: colors.textPrimary,
    fontWeight: '900',
    letterSpacing: 1.2,
    fontSize: 13,
  },
  chatCount: {
    marginLeft: 'auto',
    color: colors.textMuted,
    fontSize: 12,
    fontWeight: '700',
  },
  chatBubble: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: colors.background,
    borderRadius: radii.md,
    padding: spacing.sm,
    marginBottom: spacing.xs,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chatBubbleMine: {
    borderColor: colors.primary + '66',
    backgroundColor: '#1f1105',
  },
  chatName: {
    color: colors.textPrimary,
    fontWeight: '700',
    fontSize: 13,
    flexShrink: 1,
  },
  chatTime: {
    color: colors.textMuted,
    fontSize: 11,
  },
  chatText: {
    color: colors.textPrimary,
    fontSize: 14,
    marginTop: 2,
    lineHeight: 19,
  },
  chatInputRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 8,
    marginTop: spacing.sm,
  },
  chatInput: {
    flex: 1,
    minHeight: 44,
    maxHeight: 120,
    paddingHorizontal: spacing.md,
    paddingVertical: 10,
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.md,
    color: colors.textPrimary,
    fontSize: 15,
  },
  chatSendBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  // Live score panel
  liveScoreCard: {
    marginTop: spacing.md,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.md,
    padding: spacing.md,
  },
  liveScoreHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  livePill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 4,
    borderWidth: 1,
  },
  livePillIdle: { borderColor: colors.borderLight, backgroundColor: colors.background },
  livePillOn: { borderColor: colors.danger, backgroundColor: '#7f1d1d' },
  liveDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.textMuted,
  },
  liveDotOn: { backgroundColor: '#fff' },
  livePillText: {
    fontSize: 10,
    fontWeight: '900',
    letterSpacing: 1.2,
    color: colors.textPrimary,
  },
  liveScoreRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  liveTeam: {
    flex: 1,
    alignItems: 'center',
    gap: 6,
  },
  liveTeamLabel: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: '900',
    letterSpacing: 1.5,
    textTransform: 'uppercase',
  },
  liveControls: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  liveBtn: {
    width: 38,
    height: 38,
    borderRadius: 19,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.background,
  },
  liveBtnPlus: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  liveScore: {
    color: colors.textPrimary,
    fontSize: 36,
    fontWeight: '900',
    minWidth: 44,
    textAlign: 'center',
  },
  liveSep: {
    color: colors.textMuted,
    fontSize: 24,
    fontWeight: '900',
    paddingHorizontal: 4,
  },
});
