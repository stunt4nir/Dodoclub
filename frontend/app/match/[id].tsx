import React, { useCallback, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  Modal,
  TextInput,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter, useFocusEffect } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { api } from '../../src/api';
import { useAuth } from '../../src/auth';
import { colors, spacing, radii } from '../../src/theme';
import { Display, Overline, Muted, Title } from '../../src/typography';
import Avatar from '../../src/Avatar';

type Vote = {
  user_id: string;
  name: string;
  shirt_number: number | null;
  profile_picture: string | null;
  rating: number;
  vote: 'yes' | 'no' | 'reserve';
};

type Match = {
  id: string;
  title: string;
  date: string;
  location?: string | null;
  team_size: number;
  status: 'voting' | 'scheduled' | 'played';
  created_by?: string;
  votes: Vote[];
  lineup?: {
    team_a: Vote[];
    team_b: Vote[];
    reserves: Vote[];
    team_size: number;
  } | null;
  result?: {
    team_a_score: number;
    team_b_score: number;
    stats: { user_id: string; goals: number; assists: number }[];
    participants: string[];
  } | null;
};

function formatDate(d: string) {
  const dt = new Date(d);
  if (isNaN(dt.getTime())) return d;
  return dt.toLocaleString(undefined, {
    weekday: 'long',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formationCoords(n: number): { x: number; y: number }[] {
  // Returns coordinates in 0..1 where y=0 is top goal, y=1 is bottom goal (opponent)
  // Team A occupies bottom half (y 0.5..1). Team B (flipped) occupies top half.
  const coords: { x: number; y: number }[] = [];
  if (n === 3) {
    return [
      { x: 0.5, y: 0.94 },
      { x: 0.25, y: 0.7 },
      { x: 0.75, y: 0.7 },
    ];
  }
  if (n === 5) {
    return [
      { x: 0.5, y: 0.94 }, // GK
      { x: 0.22, y: 0.75 },
      { x: 0.78, y: 0.75 },
      { x: 0.33, y: 0.55 },
      { x: 0.67, y: 0.55 },
    ];
  }
  if (n === 7) {
    return [
      { x: 0.5, y: 0.94 },
      { x: 0.2, y: 0.78 },
      { x: 0.5, y: 0.78 },
      { x: 0.8, y: 0.78 },
      { x: 0.25, y: 0.58 },
      { x: 0.75, y: 0.58 },
      { x: 0.5, y: 0.45 },
    ];
  }
  // 11 a-side 4-4-2
  return [
    { x: 0.5, y: 0.95 },
    { x: 0.15, y: 0.82 },
    { x: 0.38, y: 0.82 },
    { x: 0.62, y: 0.82 },
    { x: 0.85, y: 0.82 },
    { x: 0.18, y: 0.65 },
    { x: 0.4, y: 0.65 },
    { x: 0.6, y: 0.65 },
    { x: 0.82, y: 0.65 },
    { x: 0.4, y: 0.5 },
    { x: 0.6, y: 0.5 },
  ];
}

function PlayerMarker({
  player,
  x,
  y,
  flip,
  accent,
}: {
  player?: Vote;
  x: number;
  y: number;
  flip?: boolean;
  accent: string;
}) {
  const ay = flip ? 1 - y : y;
  if (!player) {
    return (
      <View
        style={[
          styles.marker,
          styles.markerEmpty,
          { left: `${x * 100}%`, top: `${ay * 100}%`, borderColor: accent },
        ]}
      >
        <Text style={styles.markerEmptyText}>?</Text>
      </View>
    );
  }
  return (
    <View
      style={[
        styles.markerWrap,
        { left: `${x * 100}%`, top: `${ay * 100}%` },
      ]}
    >
      <View style={[styles.marker, { borderColor: accent }]}>
        <Text style={styles.markerNumber}>
          {player.shirt_number ?? player.name.slice(0, 1).toUpperCase()}
        </Text>
      </View>
      <Text style={styles.markerName} numberOfLines={1}>
        {player.name.split(' ')[0]}
      </Text>
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
  const [resultOpen, setResultOpen] = useState(false);
  const [scoreA, setScoreA] = useState('0');
  const [scoreB, setScoreB] = useState('0');
  const [playerStats, setPlayerStats] = useState<Record<string, { goals: string; assists: string }>>({});

  const load = useCallback(async () => {
    if (!id) return;
    try {
      const m = await api<Match>(`/matches/${id}`);
      setMatch(m);
    } catch (e: any) {
      Alert.alert('Error', e.message || 'Failed to load match');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  const canEdit = !!(user && (user.role === 'admin' || user.can_edit_matches));

  const vote = async (v: 'yes' | 'no' | 'reserve') => {
    if (!match || busy) return;
    setBusy(true);
    try {
      const updated = await api<Match>(`/matches/${match.id}/vote`, {
        method: 'POST',
        body: { vote: v },
      });
      setMatch(updated);
    } catch (e: any) {
      Alert.alert('Error', e.message || 'Vote failed');
    } finally {
      setBusy(false);
    }
  };

  const generateLineup = async () => {
    if (!match) return;
    setBusy(true);
    try {
      const updated = await api<Match>(`/matches/${match.id}/generate-lineup`, {
        method: 'POST',
      });
      setMatch(updated);
    } catch (e: any) {
      Alert.alert('Error', e.message || 'Failed');
    } finally {
      setBusy(false);
    }
  };

  const openResult = () => {
    if (!match) return;
    // ensure lineup exists (auto generate if needed via backend will handle on submit)
    const existing = match.result;
    if (existing) {
      setScoreA(String(existing.team_a_score));
      setScoreB(String(existing.team_b_score));
      const map: Record<string, { goals: string; assists: string }> = {};
      for (const s of existing.stats) {
        map[s.user_id] = { goals: String(s.goals), assists: String(s.assists) };
      }
      setPlayerStats(map);
    } else {
      setScoreA('0');
      setScoreB('0');
      setPlayerStats({});
    }
    setResultOpen(true);
  };

  const saveResult = async () => {
    if (!match) return;
    const sA = parseInt(scoreA, 10);
    const sB = parseInt(scoreB, 10);
    if (!Number.isFinite(sA) || !Number.isFinite(sB) || sA < 0 || sB < 0) {
      Alert.alert('Invalid score', 'Scores must be numbers.');
      return;
    }
    const stats = Object.entries(playerStats)
      .map(([uid, v]) => ({
        user_id: uid,
        goals: parseInt(v.goals, 10) || 0,
        assists: parseInt(v.assists, 10) || 0,
      }))
      .filter((s) => s.goals > 0 || s.assists > 0);
    setBusy(true);
    try {
      const updated = await api<Match>(`/matches/${match.id}/result`, {
        method: 'POST',
        body: { team_a_score: sA, team_b_score: sB, stats },
      });
      setMatch(updated);
      setResultOpen(false);
    } catch (e: any) {
      Alert.alert('Error', e.message || 'Failed');
    } finally {
      setBusy(false);
    }
  };

  const deleteMatch = async () => {
    if (!match) return;
    Alert.alert(
      'Delete match?',
      'This will revert any stats recorded from this match.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              await api(`/matches/${match.id}`, { method: 'DELETE' });
              router.back();
            } catch (e: any) {
              Alert.alert('Error', e.message || 'Failed');
            }
          },
        },
      ]
    );
  };

  if (loading || !match) {
    return (
      <SafeAreaView style={styles.safe}>
        <ActivityIndicator color={colors.primary} />
      </SafeAreaView>
    );
  }

  const myVote = match.votes.find((v) => v.user_id === user?.id)?.vote;
  const yesVoters = match.votes.filter((v) => v.vote === 'yes');
  const resVoters = match.votes.filter((v) => v.vote === 'reserve');
  const noVoters = match.votes.filter((v) => v.vote === 'no');
  const coords = formationCoords(match.team_size);
  const allPlayersForResult = match.lineup
    ? [...(match.lineup.team_a || []), ...(match.lineup.team_b || [])]
    : yesVoters.slice(0, match.team_size * 2);

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <ScrollView contentContainerStyle={styles.scroll}>
        {/* Header */}
        <View style={styles.headerRow}>
          <TouchableOpacity
            testID="back-btn"
            onPress={() => router.back()}
            hitSlop={12}
            style={styles.backBtn}
          >
            <Ionicons name="chevron-back" size={22} color={colors.textPrimary} />
          </TouchableOpacity>
          <Overline>{match.status.toUpperCase()}</Overline>
          {canEdit && (
            <TouchableOpacity
              testID="delete-match-btn"
              onPress={deleteMatch}
              hitSlop={12}
              style={styles.backBtn}
            >
              <Ionicons name="trash-outline" size={20} color={colors.danger} />
            </TouchableOpacity>
          )}
        </View>

        <Display style={{ fontSize: 34, lineHeight: 36 }}>{match.title}</Display>
        <Muted style={{ marginTop: 4 }}>
          {formatDate(match.date)}
          {match.location ? ` · ${match.location}` : ''}
        </Muted>
        <View style={styles.chipsRow}>
          <View style={styles.chip}>
            <Text style={styles.chipText}>{match.team_size}v{match.team_size}</Text>
          </View>
          {match.result && (
            <View style={[styles.chip, styles.scoreChip]}>
              <Text style={styles.scoreChipText}>
                {match.result.team_a_score} – {match.result.team_b_score}
              </Text>
            </View>
          )}
        </View>

        {/* Vote */}
        {match.status !== 'played' && (
          <>
            <Overline style={{ marginTop: spacing.lg, marginBottom: spacing.sm }}>
              Cast your vote
            </Overline>
            <View style={styles.voteRow}>
              <TouchableOpacity
                testID="detail-vote-yes-btn"
                disabled={busy}
                onPress={() => vote('yes')}
                activeOpacity={0.85}
                style={[
                  styles.voteCard,
                  { borderColor: colors.success, backgroundColor: 'rgba(34,197,94,0.10)' },
                  myVote === 'yes' && { backgroundColor: 'rgba(34,197,94,0.28)', borderWidth: 3 },
                ]}
              >
                <Ionicons name="checkmark-circle" size={28} color={colors.success} />
                <Text style={[styles.voteLabel, { color: colors.success }]}>YES</Text>
                <Text style={styles.voteCount}>{yesVoters.length}</Text>
              </TouchableOpacity>
              <TouchableOpacity
                testID="detail-vote-reserve-btn"
                disabled={busy}
                onPress={() => vote('reserve')}
                activeOpacity={0.85}
                style={[
                  styles.voteCard,
                  { borderColor: colors.warning, backgroundColor: 'rgba(245,158,11,0.10)' },
                  myVote === 'reserve' && { backgroundColor: 'rgba(245,158,11,0.28)', borderWidth: 3 },
                ]}
              >
                <Ionicons name="time" size={28} color={colors.warning} />
                <Text style={[styles.voteLabel, { color: colors.warning }]}>RESERVE</Text>
                <Text style={styles.voteCount}>{resVoters.length}</Text>
              </TouchableOpacity>
              <TouchableOpacity
                testID="detail-vote-no-btn"
                disabled={busy}
                onPress={() => vote('no')}
                activeOpacity={0.85}
                style={[
                  styles.voteCard,
                  { borderColor: colors.danger, backgroundColor: 'rgba(239,68,68,0.10)' },
                  myVote === 'no' && { backgroundColor: 'rgba(239,68,68,0.28)', borderWidth: 3 },
                ]}
              >
                <Ionicons name="close-circle" size={28} color={colors.danger} />
                <Text style={[styles.voteLabel, { color: colors.danger }]}>NO</Text>
                <Text style={styles.voteCount}>{noVoters.length}</Text>
              </TouchableOpacity>
            </View>
          </>
        )}

        {/* Lineup */}
        <Overline style={{ marginTop: spacing.lg, marginBottom: spacing.sm }}>
          Lineup
        </Overline>

        <View style={styles.pitch}>
          {/* Pitch markings */}
          <View style={styles.midLine} />
          <View style={styles.midCircle} />
          <View style={[styles.box, styles.boxTop]} />
          <View style={[styles.box, styles.boxBottom]} />

          {/* Team B (top, flipped) */}
          {coords.map((c, i) => (
            <PlayerMarker
              key={`b-${i}`}
              player={match.lineup?.team_b?.[i]}
              x={c.x}
              y={c.y}
              flip
              accent="#60A5FA"
            />
          ))}

          {/* Team A (bottom) */}
          {coords.map((c, i) => (
            <PlayerMarker
              key={`a-${i}`}
              player={match.lineup?.team_a?.[i]}
              x={c.x}
              y={c.y}
              accent={colors.primary}
            />
          ))}
        </View>

        <View style={styles.lineupMeta}>
          <Text style={styles.teamLabel}>
            <Text style={{ color: colors.primary }}>■ </Text>TEAM DODO
          </Text>
          <Text style={styles.teamLabel}>
            <Text style={{ color: '#60A5FA' }}>■ </Text>TEAM ORANGE
          </Text>
        </View>

        {canEdit && match.status === 'voting' && (
          <TouchableOpacity
            testID="generate-lineup-btn"
            disabled={busy || yesVoters.length === 0}
            onPress={generateLineup}
            style={[
              styles.primaryBtn,
              (busy || yesVoters.length === 0) && { opacity: 0.5 },
            ]}
            activeOpacity={0.85}
          >
            <Text style={styles.primaryBtnText}>GENERATE LINEUP</Text>
          </TouchableOpacity>
        )}

        {/* Voters breakdown */}
        <Overline style={{ marginTop: spacing.lg, marginBottom: spacing.sm }}>
          Availability ({match.votes.length})
        </Overline>
        {[
          { label: 'AVAILABLE', list: yesVoters, color: colors.success },
          { label: 'RESERVE', list: resVoters, color: colors.warning },
          { label: 'UNAVAILABLE', list: noVoters, color: colors.danger },
        ].map((g) => (
          <View key={g.label} style={styles.group}>
            <Text style={[styles.groupLabel, { color: g.color }]}>
              {g.label} · {g.list.length}
            </Text>
            {g.list.length === 0 ? (
              <Muted style={{ marginBottom: spacing.sm }}>—</Muted>
            ) : (
              g.list.map((v) => (
                <View key={v.user_id} style={styles.voterRow}>
                  <Avatar
                    uri={v.profile_picture}
                    size={36}
                    name={v.name}
                    shirt={v.shirt_number || undefined}
                  />
                  <Text style={styles.voterName}>{v.name}</Text>
                  <Text style={styles.voterRating}>{v.rating}</Text>
                </View>
              ))
            )}
          </View>
        ))}

        {canEdit && (
          <TouchableOpacity
            testID="record-result-btn"
            onPress={openResult}
            style={styles.secondaryBtn}
            activeOpacity={0.85}
          >
            <Ionicons name="stats-chart-outline" size={18} color={colors.textPrimary} />
            <Text style={styles.secondaryBtnText}>
              {match.result ? 'EDIT RESULT' : 'RECORD RESULT'}
            </Text>
          </TouchableOpacity>
        )}
      </ScrollView>

      {/* Record result modal */}
      <Modal
        visible={resultOpen}
        transparent
        animationType="slide"
        onRequestClose={() => setResultOpen(false)}
      >
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={styles.modalBg}
        >
          <View style={styles.modalCard}>
            <ScrollView showsVerticalScrollIndicator={false}>
              <View style={styles.modalHeader}>
                <Title style={{ fontSize: 20 }}>Match Result</Title>
                <TouchableOpacity
                  testID="close-result-modal"
                  onPress={() => setResultOpen(false)}
                  hitSlop={12}
                >
                  <Ionicons name="close" size={24} color={colors.textSecondary} />
                </TouchableOpacity>
              </View>

              <Text style={styles.label}>SCORE</Text>
              <View style={{ flexDirection: 'row', gap: spacing.sm, alignItems: 'center' }}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.teamSmall}>DODO</Text>
                  <TextInput
                    testID="score-team-a-input"
                    value={scoreA}
                    onChangeText={(t) => setScoreA(t.replace(/[^0-9]/g, ''))}
                    keyboardType="number-pad"
                    style={[styles.input, styles.scoreInput]}
                  />
                </View>
                <Text style={styles.vs}>VS</Text>
                <View style={{ flex: 1 }}>
                  <Text style={styles.teamSmall}>ORANGE</Text>
                  <TextInput
                    testID="score-team-b-input"
                    value={scoreB}
                    onChangeText={(t) => setScoreB(t.replace(/[^0-9]/g, ''))}
                    keyboardType="number-pad"
                    style={[styles.input, styles.scoreInput]}
                  />
                </View>
              </View>

              <Text style={[styles.label, { marginTop: spacing.md }]}>
                Player stats (goals / assists)
              </Text>
              {allPlayersForResult.length === 0 ? (
                <Muted>
                  No lineup yet. A lineup will be auto-generated from yes voters when you save.
                </Muted>
              ) : (
                allPlayersForResult.map((p) => {
                  const stat = playerStats[p.user_id] || { goals: '0', assists: '0' };
                  return (
                    <View key={p.user_id} style={styles.statRow}>
                      <Avatar
                        uri={p.profile_picture}
                        size={36}
                        name={p.name}
                        shirt={p.shirt_number || undefined}
                      />
                      <Text style={styles.statName} numberOfLines={1}>
                        {p.name}
                      </Text>
                      <TextInput
                        testID={`goals-${p.user_id}`}
                        value={stat.goals}
                        onChangeText={(t) =>
                          setPlayerStats((s) => ({
                            ...s,
                            [p.user_id]: {
                              goals: t.replace(/[^0-9]/g, ''),
                              assists: s[p.user_id]?.assists || '0',
                            },
                          }))
                        }
                        keyboardType="number-pad"
                        style={styles.statInput}
                      />
                      <Text style={styles.statDivider}>/</Text>
                      <TextInput
                        testID={`assists-${p.user_id}`}
                        value={stat.assists}
                        onChangeText={(t) =>
                          setPlayerStats((s) => ({
                            ...s,
                            [p.user_id]: {
                              goals: s[p.user_id]?.goals || '0',
                              assists: t.replace(/[^0-9]/g, ''),
                            },
                          }))
                        }
                        keyboardType="number-pad"
                        style={styles.statInput}
                      />
                    </View>
                  );
                })
              )}

              <TouchableOpacity
                testID="save-result-btn"
                disabled={busy}
                onPress={saveResult}
                style={[styles.primaryBtn, busy && { opacity: 0.5 }]}
                activeOpacity={0.85}
              >
                {busy ? (
                  <ActivityIndicator color="#fff" />
                ) : (
                  <Text style={styles.primaryBtnText}>SAVE RESULT</Text>
                )}
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
  scroll: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.xxl,
    paddingTop: spacing.md,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.sm,
  },
  backBtn: {
    width: 38,
    height: 38,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radii.md,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipsRow: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.sm },
  chip: {
    backgroundColor: colors.surfaceAccent,
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  chipText: {
    color: colors.textPrimary,
    fontWeight: '800',
    letterSpacing: 0.5,
    fontSize: 12,
  },
  scoreChip: { backgroundColor: colors.primary, borderColor: colors.primary },
  scoreChipText: { color: '#fff', fontWeight: '900', fontSize: 13 },
  voteRow: { flexDirection: 'row', gap: spacing.sm },
  voteCard: {
    flex: 1,
    aspectRatio: 1,
    borderWidth: 2,
    borderRadius: radii.md,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
    paddingVertical: spacing.sm,
  },
  voteLabel: { fontSize: 13, fontWeight: '900', letterSpacing: 1 },
  voteCount: { color: colors.textPrimary, fontSize: 18, fontWeight: '800' },
  pitch: {
    width: '100%',
    aspectRatio: 0.66,
    backgroundColor: '#14532d',
    borderRadius: radii.lg,
    borderWidth: 2,
    borderColor: '#166534',
    overflow: 'hidden',
    position: 'relative',
  },
  midLine: {
    position: 'absolute',
    top: '50%',
    left: 0,
    right: 0,
    height: 2,
    backgroundColor: 'rgba(255,255,255,0.35)',
  },
  midCircle: {
    position: 'absolute',
    top: '50%',
    left: '50%',
    width: 90,
    height: 90,
    marginLeft: -45,
    marginTop: -45,
    borderRadius: 45,
    borderWidth: 2,
    borderColor: 'rgba(255,255,255,0.35)',
  },
  box: {
    position: 'absolute',
    width: '60%',
    left: '20%',
    height: '14%',
    borderWidth: 2,
    borderColor: 'rgba(255,255,255,0.35)',
  },
  boxTop: { top: 0, borderTopWidth: 0 },
  boxBottom: { bottom: 0, borderBottomWidth: 0 },
  markerWrap: {
    position: 'absolute',
    width: 64,
    marginLeft: -32,
    marginTop: -32,
    alignItems: 'center',
  },
  marker: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.surface,
    borderWidth: 3,
    alignItems: 'center',
    justifyContent: 'center',
  },
  markerEmpty: {
    position: 'absolute',
    width: 32,
    height: 32,
    borderRadius: 16,
    marginLeft: -16,
    marginTop: -16,
    borderStyle: 'dashed',
    backgroundColor: 'rgba(255,255,255,0.07)',
  },
  markerEmptyText: {
    color: 'rgba(255,255,255,0.6)',
    fontWeight: '900',
    fontSize: 14,
  },
  markerNumber: {
    color: colors.textPrimary,
    fontWeight: '900',
    fontSize: 15,
  },
  markerName: {
    marginTop: 2,
    color: '#fff',
    fontSize: 10,
    fontWeight: '800',
    textAlign: 'center',
    textShadowColor: 'rgba(0,0,0,0.8)',
    textShadowRadius: 2,
    textShadowOffset: { width: 0, height: 1 },
  },
  lineupMeta: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: spacing.sm,
  },
  teamLabel: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: '900',
    letterSpacing: 1.2,
  },
  group: { marginBottom: spacing.md },
  groupLabel: {
    fontSize: 11,
    fontWeight: '900',
    letterSpacing: 1.5,
    marginBottom: spacing.sm,
  },
  voterRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.md,
    padding: spacing.sm,
    marginBottom: 6,
    gap: spacing.sm,
  },
  voterName: {
    flex: 1,
    color: colors.textPrimary,
    fontWeight: '700',
  },
  voterRating: {
    color: colors.primary,
    fontWeight: '900',
  },
  primaryBtn: {
    marginTop: spacing.md,
    backgroundColor: colors.primary,
    height: 50,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radii.md,
    borderBottomWidth: 4,
    borderBottomColor: colors.primaryDark,
  },
  primaryBtnText: {
    color: '#fff',
    fontSize: 15,
    fontWeight: '900',
    letterSpacing: 1,
  },
  secondaryBtn: {
    marginTop: spacing.md,
    height: 50,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    borderRadius: radii.md,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  secondaryBtnText: {
    color: colors.textPrimary,
    fontSize: 14,
    fontWeight: '900',
    letterSpacing: 1,
  },
  modalBg: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.7)',
    justifyContent: 'flex-end',
  },
  modalCard: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: radii.xl,
    borderTopRightRadius: radii.xl,
    padding: spacing.lg,
    maxHeight: '88%',
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  label: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 2,
    marginBottom: spacing.sm,
  },
  input: {
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.md,
    paddingHorizontal: spacing.md,
    height: 48,
    color: colors.textPrimary,
    fontSize: 16,
  },
  scoreInput: {
    textAlign: 'center',
    fontSize: 28,
    fontWeight: '900',
    height: 64,
  },
  teamSmall: {
    color: colors.textSecondary,
    fontSize: 10,
    fontWeight: '900',
    letterSpacing: 1.5,
    textAlign: 'center',
    marginBottom: 4,
  },
  vs: {
    color: colors.textMuted,
    fontWeight: '900',
    fontSize: 14,
    marginTop: 18,
  },
  statRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.md,
    padding: spacing.sm,
    marginBottom: 6,
  },
  statName: {
    flex: 1,
    color: colors.textPrimary,
    fontWeight: '700',
  },
  statInput: {
    width: 44,
    height: 40,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.sm,
    textAlign: 'center',
    color: colors.textPrimary,
    fontWeight: '900',
    fontSize: 16,
  },
  statDivider: { color: colors.textMuted, fontWeight: '900' },
});
