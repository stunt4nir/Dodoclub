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
  status: 'voting' | 'scheduled' | 'played';
  created_by?: string;
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
  if (n === 3) return [{ x: 0.5, y: 0.94 }, { x: 0.25, y: 0.7 }, { x: 0.75, y: 0.7 }];
  if (n === 5) return [{ x: 0.5, y: 0.94 }, { x: 0.22, y: 0.75 }, { x: 0.78, y: 0.75 }, { x: 0.33, y: 0.55 }, { x: 0.67, y: 0.55 }];
  if (n === 6) return [{ x: 0.5, y: 0.94 }, { x: 0.25, y: 0.8 }, { x: 0.75, y: 0.8 }, { x: 0.25, y: 0.6 }, { x: 0.75, y: 0.6 }, { x: 0.5, y: 0.5 }];
  if (n === 7) return [{ x: 0.5, y: 0.94 }, { x: 0.2, y: 0.78 }, { x: 0.5, y: 0.78 }, { x: 0.8, y: 0.78 }, { x: 0.25, y: 0.58 }, { x: 0.75, y: 0.58 }, { x: 0.5, y: 0.45 }];
  return [{ x: 0.5, y: 0.95 }, { x: 0.15, y: 0.82 }, { x: 0.38, y: 0.82 }, { x: 0.62, y: 0.82 }, { x: 0.85, y: 0.82 }, { x: 0.18, y: 0.65 }, { x: 0.4, y: 0.65 }, { x: 0.6, y: 0.65 }, { x: 0.82, y: 0.65 }, { x: 0.4, y: 0.5 }, { x: 0.6, y: 0.5 }];
}

function PlayerMarker({ player, x, y, flip, color, textColor }: {
  player?: Vote; x: number; y: number; flip?: boolean; color: string; textColor: string;
}) {
  const ay = flip ? 1 - y : y;
  if (!player) {
    return <View style={[styles.markerEmpty, { left: `${x * 100}%`, top: `${ay * 100}%`, borderColor: color }]}>
      <Text style={styles.markerEmptyText}>?</Text>
    </View>;
  }
  return (
    <View style={[styles.markerWrap, { left: `${x * 100}%`, top: `${ay * 100}%` }]}>
      <View style={[styles.marker, { backgroundColor: color, borderColor: color }]}>
        <Text style={[styles.markerNumber, { color: textColor }]}>
          {player.shirt_number ?? player.name.slice(0, 1).toUpperCase()}
        </Text>
      </View>
      <Text style={styles.markerName} numberOfLines={1}>{player.name.split(' ')[0]}</Text>
    </View>
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

  const load = useCallback(async () => {
    if (!id) return;
    try {
      const m = await api<Match>(`/matches/${id}`);
      setMatch(m);
    } catch (e: any) { Alert.alert('Error', e.message || 'Failed to load match'); }
    finally { setLoading(false); }
  }, [id]);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  // live timer tick
  useEffect(() => {
    if (!match?.timer_started_at || match?.timer_ended_at) return;
    const t = setInterval(() => setTickTock((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, [match?.timer_started_at, match?.timer_ended_at]);

  const canEdit = !!(user && (user.role === 'admin' || user.can_edit_matches));

  const vote = async (v: 'yes' | 'no' | 'reserve') => {
    if (!match || busy) return;
    setBusy(true);
    try {
      const updated = await api<Match>(`/matches/${match.id}/vote`, { method: 'POST', body: { vote: v } });
      setMatch(updated);
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
      setScoreA(0); setScoreB(0); setScoreC(0); setPlayerStats({});
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
      preferred_position: null,
      rating: 0,
      vote: 'yes' as any,
    };
    (entry as any).is_guest = true;
    (entry as any).guest_name = guestName.trim();
    (entry as any).guest_shirt = entry.shirt_number;
    setDraftExtras((prev) => [...prev, entry]);
    setDraftBuckets((b) => ({ ...b, [tempId]: 'reserves' }));
    setGuestName('');
    setGuestShirt('');
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
                  <Ionicons name={vc.icon} size={28} color={vc.color} />
                  <Text style={[styles.voteLabel, { color: vc.color }]}>{vc.label}</Text>
                  <Text style={styles.voteCount}>{vc.count}</Text>
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
            <PlayerMarker key={`b-${i}`} player={teamB[i]} x={c.x} y={c.y} flip color={TEAM_COLORS.b.primary} textColor={TEAM_COLORS.b.text} />
          ))}
          {coords.map((c, i) => (
            <PlayerMarker key={`a-${i}`} player={teamA[i]} x={c.x} y={c.y} color={TEAM_COLORS.a.primary} textColor={TEAM_COLORS.a.text} />
          ))}
        </View>

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
                    {v.preferred_position && <View style={styles.posBadge}><Text style={styles.posBadgeText}>{v.preferred_position}</Text></View>}
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

              <Text style={[styles.label, { marginTop: spacing.md }]}>Tap + to add goals & assists</Text>
              {allPlayersForResult.length === 0 ? (
                <Muted>No lineup yet. A lineup will be auto-generated from yes voters when you save.</Muted>
              ) : (
                allPlayersForResult.map((p) => {
                  const stat = playerStats[p.user_id] || { goals: 0, assists: 0 };
                  return (
                    <View key={p.user_id} style={styles.statRow}>
                      <Avatar uri={p.profile_picture} size={36} name={p.name} shirt={p.shirt_number || undefined} />
                      <Text style={styles.statName} numberOfLines={1}>{p.name}</Text>
                      <View style={{ alignItems: 'center', gap: 2 }}>
                        <Text style={styles.statLabel}>GOAL</Text>
                        <Stepper
                          testID={`goals-${p.user_id}`}
                          value={stat.goals}
                          onChange={(v) => setPlayerStats((s) => ({ ...s, [p.user_id]: { goals: v, assists: s[p.user_id]?.assists || 0 } }))}
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
                        {u.preferred_position && (
                          <View style={styles.posBadge}>
                            <Text style={styles.posBadgeText}>{u.preferred_position}</Text>
                          </View>
                        )}
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
                    placeholderTextColor={colors.textMuted}
                    style={[styles.input, { flex: 1 }]}
                  />
                  <TextInput
                    testID="guest-shirt-input"
                    value={guestShirt}
                    onChangeText={(t) => setGuestShirt(t.replace(/[^0-9]/g, '').slice(0, 2))}
                    keyboardType="number-pad"
                    placeholder="#"
                    placeholderTextColor={colors.textMuted}
                    style={[styles.input, { width: 60, textAlign: 'center' }]}
                  />
                  <TouchableOpacity
                    testID="add-guest-btn"
                    onPress={addGuestToLineup}
                    style={styles.guestAddBtn}
                    activeOpacity={0.85}
                  >
                    <Ionicons name="add" size={20} color="#fff" />
                  </TouchableOpacity>
                </View>
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
  midLine: { position: 'absolute', top: '50%', left: 0, right: 0, height: 2, backgroundColor: 'rgba(255,255,255,0.35)' },
  midCircle: { position: 'absolute', top: '50%', left: '50%', width: 90, height: 90, marginLeft: -45, marginTop: -45, borderRadius: 45, borderWidth: 2, borderColor: 'rgba(255,255,255,0.35)' },
  box: { position: 'absolute', width: '60%', left: '20%', height: '14%', borderWidth: 2, borderColor: 'rgba(255,255,255,0.35)' },
  boxTop: { top: 0, borderTopWidth: 0 },
  boxBottom: { bottom: 0, borderBottomWidth: 0 },
  markerWrap: { position: 'absolute', width: 64, marginLeft: -32, marginTop: -32, alignItems: 'center' },
  marker: { width: 44, height: 44, borderRadius: 22, borderWidth: 3, alignItems: 'center', justifyContent: 'center' },
  markerEmpty: { position: 'absolute', width: 32, height: 32, borderRadius: 16, marginLeft: -16, marginTop: -16, borderStyle: 'dashed', backgroundColor: 'rgba(255,255,255,0.07)', borderWidth: 2, alignItems: 'center', justifyContent: 'center' },
  markerEmptyText: { color: 'rgba(255,255,255,0.6)', fontWeight: '900', fontSize: 14 },
  markerNumber: { fontWeight: '900', fontSize: 15 },
  markerName: { marginTop: 2, color: '#fff', fontSize: 10, fontWeight: '800', textAlign: 'center' },
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
});
