import React, { useCallback, useMemo, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
  Modal,
  TextInput,
  KeyboardAvoidingView,
  Platform,
  Alert,
  ScrollView,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useFocusEffect, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { api } from '../../src/api';
import { useAuth } from '../../src/auth';
import { confirm } from '../../src/confirm';
import { colors, spacing, radii } from '../../src/theme';
import { Display, Overline, Muted, Title } from '../../src/typography';
import Avatar from '../../src/Avatar';

type StandingRow = {
  team: string;
  P: number; W: number; D: number; L: number;
  GF: number; GA: number; GD: number; Pts: number;
};
type Fixture = {
  match_id: string;
  home: string;
  away: string;
  round: number;
  scheduled_at: string | null;
  played: boolean;
  live: boolean;
  score_home: number | null;
  score_away: number | null;
  scorers: { user_id: string; goals: number }[];
  assisters: { user_id: string; assists: number }[];
};
type Tournament = {
  id: string;
  name: string;
  team_names: string[];
  team_size: number;
  match_type: 'friendly' | 'league';
  team_rosters: Record<string, string[]>;
  created_at: string;
  fixtures: Fixture[];
  standings: StandingRow[];
  winner: string | null;
  completed: boolean;
};
type SquadUser = {
  id: string;
  name: string;
  shirt_number: number | null;
  profile_picture: string | null;
  preferred_position: string | null;
  rating: number;
};

function todayPlusDays(d: number): Date {
  const out = new Date();
  out.setDate(out.getDate() + d);
  return out;
}
function formatDate(iso: string | null) {
  if (!iso) return '';
  const dt = new Date(iso);
  if (isNaN(dt.getTime())) return '';
  return dt.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
}

// Default Club Dodo team palettes
const DEFAULT_TEAMS = ['Red', 'Black', 'White', 'Blue'];
const TEAM_COLORS: Record<string, string> = {
  Red: '#EF4444',
  Black: '#3F3F46',
  White: '#E5E7EB',
  Blue: '#3B82F6',
  Green: '#22C55E',
  Yellow: '#EAB308',
  Orange: '#F97316',
  Purple: '#A855F7',
};
function colorFor(name: string): string {
  return TEAM_COLORS[name] || colors.primary;
}

export default function TournamentsScreen() {
  const router = useRouter();
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const [items, setItems] = useState<Tournament[] | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [modalOpen, setModalOpen] = useState(false);
  const [addMatchFor, setAddMatchFor] = useState<Tournament | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await api<Tournament[]>('/tournaments');
      setItems(res);
    } catch (e: any) {
      Alert.alert('Failed to load tournaments', e?.message || 'Network error');
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  // Auto-refresh every 10s if any tournament has a live fixture, so standings
  // reflect the running scores without manual pull-to-refresh.
  React.useEffect(() => {
    if (!items) return;
    const hasLive = items.some((t) => t.fixtures.some((f) => f.live));
    if (!hasLive) return;
    const id = setInterval(() => {
      load();
    }, 10000);
    return () => clearInterval(id);
  }, [items, load]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  }, [load]);

  const deleteTournament = async (t: Tournament) => {
    const ok = await confirm(
      'Delete tournament?',
      `"${t.name}" and all ${t.fixtures.length} fixtures will be removed.`,
    );
    if (!ok) return;
    try {
      await api(`/tournaments/${t.id}`, { method: 'DELETE' });
      await load();
    } catch (e: any) {
      Alert.alert('Failed', e?.message || 'Delete failed');
    }
  };

  const toggle = (id: string) => setExpanded((m) => ({ ...m, [id]: !m[id] }));

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <View style={styles.header}>
        <View style={{ flex: 1 }}>
          <Overline>Round-Robin</Overline>
          <Display style={{ fontSize: 30 }}>Cups</Display>
        </View>
        {isAdmin && (
          <TouchableOpacity
            testID="create-tournament-btn"
            onPress={() => setModalOpen(true)}
            style={styles.createBtn}
            activeOpacity={0.85}
          >
            <Ionicons name="add" size={20} color="#fff" />
            <Text style={styles.createBtnText}>NEW</Text>
          </TouchableOpacity>
        )}
      </View>

      {items === null ? (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <ActivityIndicator color={colors.primary} />
        </View>
      ) : (
        <FlatList
          data={items}
          keyExtractor={(t) => t.id}
          contentContainerStyle={styles.list}
          refreshControl={<RefreshControl tintColor={colors.primary} refreshing={refreshing} onRefresh={onRefresh} />}
          ListEmptyComponent={
            <Muted style={{ textAlign: 'center', marginTop: 40 }}>
              No tournaments yet{isAdmin ? ' — tap NEW to create one.' : '.'}
            </Muted>
          }
          renderItem={({ item }) => (
            <TournamentCard
              t={item}
              expanded={!!expanded[item.id]}
              onToggle={() => toggle(item.id)}
              onOpenMatch={(mid) => router.push(`/match/${mid}`)}
              onDelete={isAdmin ? () => deleteTournament(item) : undefined}
              onAddMatch={isAdmin ? () => setAddMatchFor(item) : undefined}
            />
          )}
        />
      )}

      <CreateTournamentModal
        visible={modalOpen}
        onClose={() => setModalOpen(false)}
        onCreated={async () => {
          setModalOpen(false);
          await load();
        }}
      />

      <AddMatchModal
        tournament={addMatchFor}
        onClose={() => setAddMatchFor(null)}
        onCreated={async () => {
          setAddMatchFor(null);
          await load();
        }}
      />
    </SafeAreaView>
  );
}

// ============================================================================
// Tournament Card
// ============================================================================
function TournamentCard({
  t,
  expanded,
  onToggle,
  onOpenMatch,
  onDelete,
  onAddMatch,
}: {
  t: Tournament;
  expanded: boolean;
  onToggle: () => void;
  onOpenMatch: (mid: string) => void;
  onDelete?: () => void;
  onAddMatch?: () => void;
}) {
  const playedCount = t.fixtures.filter((f) => f.played).length;
  const liveCount = t.fixtures.filter((f) => f.live).length;
  return (
    <View style={styles.cardWrap}>
      <TouchableOpacity activeOpacity={0.85} onPress={onToggle} style={styles.card}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: spacing.sm }}>
          <View style={styles.trophyIcon}>
            <Ionicons name="trophy" size={20} color={colors.primary} />
          </View>
          <View style={{ flex: 1 }}>
            <Title style={{ fontSize: 18 }} numberOfLines={1}>{t.name}</Title>
            <Muted style={{ fontSize: 12 }}>
              {t.team_names.length} teams · {t.team_size}v{t.team_size} · {playedCount}/{t.fixtures.length} played
            </Muted>
          </View>
          {liveCount > 0 && (
            <View style={[styles.tag, { borderColor: colors.danger, backgroundColor: '#7f1d1d' }]}>
              <View style={styles.liveBadgeDot} />
              <Text style={[styles.tagText, { color: '#fff' }]}> {liveCount} LIVE</Text>
            </View>
          )}
          {t.completed && t.winner && (
            <View style={[styles.tag, { borderColor: colors.success }]}>
              <Text style={[styles.tagText, { color: colors.success }]}>{t.winner.toUpperCase()} WINS</Text>
            </View>
          )}
          <Ionicons name={expanded ? 'chevron-up' : 'chevron-down'} size={18} color={colors.textSecondary} />
        </View>

        {/* Team chips */}
        <View style={styles.teamChipsRow}>
          {t.team_names.map((n) => (
            <View key={n} style={[styles.teamChip, { borderColor: colorFor(n) }]}>
              <View style={[styles.teamDot, { backgroundColor: colorFor(n) }]} />
              <Text style={styles.teamChipText}>{n}</Text>
            </View>
          ))}
        </View>
      </TouchableOpacity>

      {expanded && (
        <View style={styles.expanded}>
          {/* Standings */}
          <Overline style={{ marginBottom: spacing.sm }}>Standings</Overline>
          <View style={styles.tableHeader}>
            <Text style={[styles.th, { flex: 2 }]}>Team</Text>
            <Text style={styles.th}>P</Text>
            <Text style={styles.th}>W</Text>
            <Text style={styles.th}>D</Text>
            <Text style={styles.th}>L</Text>
            <Text style={styles.th}>GD</Text>
            <Text style={[styles.th, { color: colors.primary }]}>Pts</Text>
          </View>
          {t.standings.map((s, i) => (
            <View key={s.team} style={[styles.tableRow, i === 0 && t.completed && { backgroundColor: colors.surfaceAccent }]}>
              <View style={[styles.tdTeam, { flex: 2 }]}>
                <View style={[styles.teamDot, { backgroundColor: colorFor(s.team) }]} />
                <Text style={styles.td}>{s.team}</Text>
              </View>
              <Text style={styles.td}>{s.P}</Text>
              <Text style={styles.td}>{s.W}</Text>
              <Text style={styles.td}>{s.D}</Text>
              <Text style={styles.td}>{s.L}</Text>
              <Text style={[styles.td, { color: s.GD > 0 ? colors.success : s.GD < 0 ? colors.danger : colors.textSecondary }]}>
                {s.GD > 0 ? `+${s.GD}` : s.GD}
              </Text>
              <Text style={[styles.td, { color: colors.primary, fontWeight: '900' }]}>{s.Pts}</Text>
            </View>
          ))}

          {/* Fixtures */}
          <Overline style={{ marginTop: spacing.lg, marginBottom: spacing.sm }}>Fixtures</Overline>
          {t.fixtures.map((f) => (
            <TouchableOpacity
              key={f.match_id}
              testID={`fixture-${f.match_id}`}
              onPress={() => onOpenMatch(f.match_id)}
              style={[
                styles.fixture,
                f.played && styles.fixturePlayed,
                f.live && styles.fixtureLive,
              ]}
              activeOpacity={0.7}
            >
              <View style={styles.fixtureRoundCol}>
                <Text style={styles.fixtureRound}>R{f.round}</Text>
                {f.live ? (
                  <View style={styles.liveBadge} testID={`fixture-${f.match_id}-live-badge`}>
                    <View style={styles.liveBadgeDot} />
                    <Text style={styles.liveBadgeText}>LIVE</Text>
                  </View>
                ) : (
                  <Muted style={{ fontSize: 10 }}>{formatDate(f.scheduled_at)}</Muted>
                )}
              </View>
              <View style={styles.fixtureTeams}>
                <View style={styles.fixtureTeamRow}>
                  <View style={[styles.teamDot, { backgroundColor: colorFor(f.home) }]} />
                  <Text style={styles.fixtureTeam} numberOfLines={1}>{f.home}</Text>
                  <Text style={[
                    styles.fixtureScore,
                    !f.played && !f.live && { color: colors.textMuted },
                    f.live && { color: colors.danger },
                  ]}>
                    {(f.played || f.live) && f.score_home != null ? f.score_home : '-'}
                  </Text>
                </View>
                <View style={styles.fixtureTeamRow}>
                  <View style={[styles.teamDot, { backgroundColor: colorFor(f.away) }]} />
                  <Text style={styles.fixtureTeam} numberOfLines={1}>{f.away}</Text>
                  <Text style={[
                    styles.fixtureScore,
                    !f.played && !f.live && { color: colors.textMuted },
                    f.live && { color: colors.danger },
                  ]}>
                    {(f.played || f.live) && f.score_away != null ? f.score_away : '-'}
                  </Text>
                </View>
              </View>
              <Ionicons name="chevron-forward" size={16} color={colors.textMuted} />
            </TouchableOpacity>
          ))}

          {onDelete && (
            <View style={{ flexDirection: 'row', gap: spacing.sm, marginTop: spacing.md }}>
              {onAddMatch && (
                <TouchableOpacity
                  testID={`add-match-tournament-${t.id}`}
                  onPress={onAddMatch}
                  style={[styles.dangerBtn, { borderColor: colors.primary, flex: 1 }]}
                  activeOpacity={0.85}
                >
                  <Ionicons name="add-circle-outline" size={16} color={colors.primary} />
                  <Text style={[styles.dangerBtnText, { color: colors.primary }]}>ADD MATCH</Text>
                </TouchableOpacity>
              )}
              <TouchableOpacity
                testID={`delete-tournament-${t.id}`}
                onPress={onDelete}
                style={[styles.dangerBtn, { flex: 1 }]}
                activeOpacity={0.85}
              >
                <Ionicons name="trash-outline" size={16} color={colors.danger} />
                <Text style={styles.dangerBtnText}>DELETE</Text>
              </TouchableOpacity>
            </View>
          )}
        </View>
      )}
    </View>
  );
}

// ============================================================================
// Create Tournament Modal
// ============================================================================
function CreateTournamentModal({
  visible,
  onClose,
  onCreated,
}: {
  visible: boolean;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState('');
  const [teamSize, setTeamSize] = useState(5);
  const [matchType, setMatchType] = useState<'friendly' | 'league'>('friendly');
  const [dateOffset, setDateOffset] = useState(1);
  const [startTime, setStartTime] = useState('19:00');
  const [allSameDate, setAllSameDate] = useState(false);
  const [doubleRR, setDoubleRR] = useState(false);
  const [teams, setTeams] = useState<string[]>(['Red', 'Black', 'White']);
  // user_id -> team_name (or undefined = unassigned)
  const [assigns, setAssigns] = useState<Record<string, string>>({});
  const [squad, setSquad] = useState<SquadUser[] | null>(null);
  const [saving, setSaving] = useState(false);

  React.useEffect(() => {
    if (!visible) return;
    // Reset state on each open
    setName('');
    setTeamSize(5);
    setMatchType('friendly');
    setDateOffset(1);
    setStartTime('19:00');
    setAllSameDate(false);
    setDoubleRR(false);
    setTeams(['Red', 'Black', 'White']);
    setAssigns({});
    setSaving(false);
    (async () => {
      try {
        const res = await api<SquadUser[]>('/users');
        setSquad(res);
      } catch (e: any) {
        Alert.alert('Failed to load squad', e?.message || 'Network error');
      }
    })();
  }, [visible]);

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const t of teams) c[t] = 0;
    for (const team of Object.values(assigns)) {
      if (team && c[team] !== undefined) c[team] += 1;
    }
    return c;
  }, [assigns, teams]);

  const addTeam = () => {
    if (teams.length >= 8) return;
    const candidates = DEFAULT_TEAMS.filter((d) => !teams.includes(d));
    const fallback = `Team ${teams.length + 1}`;
    setTeams([...teams, candidates[0] || fallback]);
  };
  const removeTeam = (idx: number) => {
    if (teams.length <= 2) return;
    const removed = teams[idx];
    const next = teams.filter((_, i) => i !== idx);
    setTeams(next);
    // Unassign any players on the removed team
    setAssigns((prev) => {
      const out: Record<string, string> = {};
      for (const [uid, t] of Object.entries(prev)) {
        if (t !== removed) out[uid] = t;
      }
      return out;
    });
  };
  const renameTeam = (idx: number, newName: string) => {
    const trimmed = newName.replace(/[^A-Za-z0-9 ]/g, '').slice(0, 20);
    const old = teams[idx];
    const next = [...teams];
    next[idx] = trimmed;
    setTeams(next);
    if (old !== trimmed) {
      setAssigns((prev) => {
        const out: Record<string, string> = {};
        for (const [uid, t] of Object.entries(prev)) {
          out[uid] = t === old ? trimmed : t;
        }
        return out;
      });
    }
  };
  const cycleAssign = (uid: string) => {
    setAssigns((prev) => {
      const cur = prev[uid];
      const order = ['', ...teams];
      const i = order.indexOf(cur || '');
      const nextVal = order[(i + 1) % order.length];
      const out = { ...prev };
      if (!nextVal) delete out[uid];
      else out[uid] = nextVal;
      return out;
    });
  };

  const submit = async () => {
    if (!name.trim()) {
      Alert.alert('Missing name', 'Please give the tournament a name.');
      return;
    }
    const cleanTeams = teams.map((t) => t.trim()).filter((t) => t.length > 0);
    if (new Set(cleanTeams).size !== cleanTeams.length) {
      Alert.alert('Duplicate team names', 'Each team must have a unique name.');
      return;
    }
    if (cleanTeams.length < 2) {
      Alert.alert('Need 2+ teams', 'Add at least two teams.');
      return;
    }

    // Build rosters
    const rosters: Record<string, string[]> = {};
    for (const t of cleanTeams) rosters[t] = [];
    for (const [uid, team] of Object.entries(assigns)) {
      if (team && rosters[team]) rosters[team].push(uid);
    }

    // Check that no team exceeds team_size
    for (const t of cleanTeams) {
      if (rosters[t].length > teamSize) {
        Alert.alert('Roster too large', `Team "${t}" has ${rosters[t].length} players (max ${teamSize}).`);
        return;
      }
    }

    const totalAssigned = Object.values(assigns).filter(Boolean).length;
    if (totalAssigned === 0) {
      Alert.alert('No players assigned', 'Tap the chips next to each player to assign them to a team.');
      return;
    }

    const start = todayPlusDays(dateOffset);
    const ymd = start.toISOString().slice(0, 10);

    setSaving(true);
    try {
      await api('/tournaments', {
        method: 'POST',
        body: {
          name: name.trim(),
          team_names: cleanTeams,
          team_size: teamSize,
          match_type: matchType,
          start_date: ymd,
          start_time: startTime,
          all_same_date: allSameDate,
          double_round_robin: doubleRR,
          team_rosters: rosters,
        },
      });
      onCreated();
    } catch (e: any) {
      Alert.alert('Failed', e?.message || 'Create failed');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={styles.modalBg}
      >
        <View style={styles.modalCard}>
          <View style={styles.modalHeader}>
            <Title style={{ fontSize: 20 }}>New Tournament</Title>
            <TouchableOpacity testID="close-create-tournament-modal" onPress={onClose} hitSlop={12}>
              <Ionicons name="close" size={24} color={colors.textSecondary} />
            </TouchableOpacity>
          </View>

          <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{ paddingBottom: spacing.lg }}>
            <Text style={styles.label}>NAME</Text>
            <TextInput
              testID="tournament-name-input"
              value={name}
              onChangeText={setName}
              placeholder="Summer Cup 2026"
              placeholderTextColor={colors.textMuted}
              style={styles.input}
            />

            <Text style={[styles.label, { marginTop: spacing.md }]}>MATCH TYPE</Text>
            <View style={styles.row}>
              {(['friendly', 'league'] as const).map((t) => (
                <TouchableOpacity
                  key={t}
                  testID={`tournament-type-${t}-btn`}
                  onPress={() => setMatchType(t)}
                  style={[styles.choice, matchType === t && styles.choiceActive]}
                  activeOpacity={0.8}
                >
                  <Text style={[styles.choiceText, matchType === t && styles.choiceTextActive]}>
                    {t.toUpperCase()}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            <Text style={[styles.label, { marginTop: spacing.md }]}>TEAM SIZE</Text>
            <View style={styles.row}>
              {[4, 5, 6, 7, 8, 9, 11].map((n) => (
                <TouchableOpacity
                  key={n}
                  testID={`tournament-size-${n}-btn`}
                  onPress={() => setTeamSize(n)}
                  style={[styles.choice, teamSize === n && styles.choiceActive]}
                  activeOpacity={0.8}
                >
                  <Text style={[styles.choiceText, teamSize === n && styles.choiceTextActive]}>
                    {n}v{n}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            <Text style={[styles.label, { marginTop: spacing.md }]}>FIRST FIXTURE DATE</Text>
            <View style={styles.row}>
              {[0, 1, 2, 3, 4, 5, 6].map((n) => {
                const d = todayPlusDays(n);
                const short = n === 0
                  ? 'Today'
                  : d.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric' });
                return (
                  <TouchableOpacity
                    key={n}
                    testID={`tournament-date-${n}-btn`}
                    onPress={() => setDateOffset(n)}
                    style={[styles.choice, dateOffset === n && styles.choiceActive]}
                    activeOpacity={0.8}
                  >
                    <Text style={[styles.choiceText, dateOffset === n && styles.choiceTextActive]}>
                      {short}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>
            <Muted style={{ fontSize: 11, marginTop: 4 }}>
              {allSameDate
                ? 'All fixtures on the chosen date — start at the time below, +1 hour each.'
                : doubleRR
                  ? 'Each pair plays twice. One fixture per day at the time below.'
                  : 'Subsequent fixtures are scheduled one per day at the time below.'}
            </Muted>

            <Text style={[styles.label, { marginTop: spacing.md }]}>KICK-OFF TIME (HH:MM)</Text>
            <TextInput
              testID="tournament-time-input"
              value={startTime}
              onChangeText={(v) => {
                // Lightly normalise: keep digits and one ':'
                const cleaned = v.replace(/[^\d:]/g, '').slice(0, 5);
                setStartTime(cleaned);
              }}
              placeholder="19:00"
              placeholderTextColor={colors.textMuted}
              style={[styles.input, { width: 120 }]}
              keyboardType="numbers-and-punctuation"
            />

            <View style={[styles.toggleRow, { marginTop: spacing.md }]}>
              <View style={{ flex: 1 }}>
                <Text style={styles.toggleLabel}>ALL ON SAME DATE</Text>
                <Muted style={{ fontSize: 11 }}>
                  Stack every fixture on the chosen date (kick-off, +1h, +2h…).
                </Muted>
              </View>
              <TouchableOpacity
                testID="tournament-same-date-toggle"
                onPress={() => setAllSameDate((v) => !v)}
                style={[styles.toggle, allSameDate && styles.toggleOn]}
                activeOpacity={0.8}
              >
                <View style={[styles.toggleKnob, allSameDate && styles.toggleKnobOn]} />
              </TouchableOpacity>
            </View>

            <View style={styles.toggleRow}>
              <View style={{ flex: 1 }}>
                <Text style={styles.toggleLabel}>DOUBLE ROUND-ROBIN</Text>
                <Muted style={{ fontSize: 11 }}>
                  Each pair plays twice (home & away).
                </Muted>
              </View>
              <TouchableOpacity
                testID="tournament-double-rr-toggle"
                onPress={() => setDoubleRR((v) => !v)}
                style={[styles.toggle, doubleRR && styles.toggleOn]}
                activeOpacity={0.8}
              >
                <View style={[styles.toggleKnob, doubleRR && styles.toggleKnobOn]} />
              </TouchableOpacity>
            </View>

            {/* Teams editor */}
            <View style={styles.sectionHeader}>
              <Text style={styles.label}>TEAMS ({teams.length})</Text>
              <TouchableOpacity
                testID="add-team-btn"
                onPress={addTeam}
                disabled={teams.length >= 8}
                style={[styles.miniBtn, teams.length >= 8 && { opacity: 0.4 }]}
              >
                <Ionicons name="add" size={14} color={colors.primary} />
                <Text style={styles.miniBtnText}>ADD</Text>
              </TouchableOpacity>
            </View>
            {teams.map((t, idx) => (
              <View key={`${idx}-${t}`} style={styles.teamRow}>
                <View style={[styles.teamColorSwatch, { backgroundColor: colorFor(t) }]} />
                <TextInput
                  testID={`team-name-input-${idx}`}
                  value={t}
                  onChangeText={(v) => renameTeam(idx, v)}
                  placeholder="Team name"
                  placeholderTextColor={colors.textMuted}
                  style={[styles.input, { flex: 1 }]}
                />
                <Muted style={{ width: 50, textAlign: 'center' }}>
                  {counts[t] || 0}/{teamSize}
                </Muted>
                <TouchableOpacity
                  testID={`remove-team-${idx}`}
                  onPress={() => removeTeam(idx)}
                  disabled={teams.length <= 2}
                  style={[styles.iconBtn, teams.length <= 2 && { opacity: 0.3 }]}
                >
                  <Ionicons name="trash-outline" size={16} color={colors.danger} />
                </TouchableOpacity>
              </View>
            ))}

            {/* Squad assignment */}
            <Text style={[styles.label, { marginTop: spacing.md }]}>ASSIGN PLAYERS</Text>
            <Muted style={{ fontSize: 11, marginBottom: spacing.sm }}>
              Tap each player's chip to cycle through teams.
            </Muted>
            {squad === null ? (
              <ActivityIndicator color={colors.primary} style={{ marginVertical: spacing.md }} />
            ) : (
              squad.map((p) => {
                const team = assigns[p.id];
                return (
                  <View key={p.id} style={styles.playerRow}>
                    <Avatar uri={p.profile_picture} size={36} shirt={p.shirt_number} name={p.name} />
                    <View style={{ flex: 1, marginLeft: spacing.sm }}>
                      <Text style={styles.playerName} numberOfLines={1}>{p.name}</Text>
                      <Muted style={{ fontSize: 11 }}>
                        {p.preferred_position || '—'} · ★ {p.rating?.toFixed?.(1) || '0.0'}
                      </Muted>
                    </View>
                    <TouchableOpacity
                      testID={`assign-player-${p.id}`}
                      onPress={() => cycleAssign(p.id)}
                      style={[
                        styles.assignChip,
                        team
                          ? { backgroundColor: colorFor(team), borderColor: colorFor(team) }
                          : { borderColor: colors.borderLight },
                      ]}
                      activeOpacity={0.8}
                    >
                      <Text style={[styles.assignChipText, team && team !== 'White' && { color: '#fff' }]}>
                        {team || 'UNASSIGNED'}
                      </Text>
                    </TouchableOpacity>
                  </View>
                );
              })
            )}

            <TouchableOpacity
              testID="submit-create-tournament-btn"
              disabled={saving}
              onPress={submit}
              style={[styles.primaryBtn, saving && { opacity: 0.6 }]}
              activeOpacity={0.85}
            >
              {saving ? <ActivityIndicator color="#fff" /> : <Text style={styles.primaryBtnText}>CREATE TOURNAMENT</Text>}
            </TouchableOpacity>
          </ScrollView>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

// ============================================================================
// Add Match Modal — append a custom fixture to an existing tournament
// ============================================================================
function AddMatchModal({
  tournament,
  onClose,
  onCreated,
}: {
  tournament: Tournament | null;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [home, setHome] = useState<string | null>(null);
  const [away, setAway] = useState<string | null>(null);
  const [dateOffset, setDateOffset] = useState(0);
  const [time, setTime] = useState('19:00');
  const [saving, setSaving] = useState(false);

  React.useEffect(() => {
    if (!tournament) return;
    setHome(tournament.team_names[0] || null);
    setAway(tournament.team_names[1] || null);
    setDateOffset(0);
    setTime('19:00');
    setSaving(false);
  }, [tournament]);

  if (!tournament) return null;

  const submit = async () => {
    if (!home || !away) {
      Alert.alert('Pick teams', 'Choose home and away.');
      return;
    }
    if (home === away) {
      Alert.alert('Same team', 'Home and away must be different.');
      return;
    }
    if (!/^\d{1,2}:\d{2}$/.test(time)) {
      Alert.alert('Bad time', 'Use HH:MM (24h).');
      return;
    }
    const d = todayPlusDays(dateOffset);
    const [hhStr, mmStr] = time.split(':');
    const hh = Math.max(0, Math.min(23, parseInt(hhStr || '19', 10) || 19));
    const mm = Math.max(0, Math.min(59, parseInt(mmStr || '0', 10) || 0));
    d.setHours(hh, mm, 0, 0);
    const iso = d.toISOString();
    setSaving(true);
    try {
      await api(`/tournaments/${tournament.id}/matches`, {
        method: 'POST',
        body: { home, away, scheduled_at: iso },
      });
      onCreated();
    } catch (e: any) {
      Alert.alert('Failed', e?.message || 'Could not add match');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal visible={!!tournament} transparent animationType="slide" onRequestClose={onClose}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        style={styles.modalBg}
      >
        <View style={styles.modalCard}>
          <View style={styles.modalHeader}>
            <Title style={{ fontSize: 20 }}>Add Fixture</Title>
            <TouchableOpacity testID="close-add-match-modal" onPress={onClose} hitSlop={12}>
              <Ionicons name="close" size={24} color={colors.textSecondary} />
            </TouchableOpacity>
          </View>
          <Muted style={{ marginBottom: spacing.md }}>{tournament.name}</Muted>

          <Text style={styles.label}>HOME TEAM</Text>
          <View style={styles.row}>
            {tournament.team_names.map((t) => (
              <TouchableOpacity
                key={`home-${t}`}
                testID={`add-match-home-${t}`}
                onPress={() => setHome(t)}
                style={[
                  styles.choice,
                  home === t && {
                    backgroundColor: colorFor(t),
                    borderColor: colorFor(t),
                  },
                ]}
                activeOpacity={0.8}
              >
                <Text style={[
                  styles.choiceText,
                  home === t && t !== 'White' && { color: '#fff' },
                ]}>
                  {t.toUpperCase()}
                </Text>
              </TouchableOpacity>
            ))}
          </View>

          <Text style={[styles.label, { marginTop: spacing.md }]}>AWAY TEAM</Text>
          <View style={styles.row}>
            {tournament.team_names.map((t) => (
              <TouchableOpacity
                key={`away-${t}`}
                testID={`add-match-away-${t}`}
                onPress={() => setAway(t)}
                disabled={t === home}
                style={[
                  styles.choice,
                  away === t && {
                    backgroundColor: colorFor(t),
                    borderColor: colorFor(t),
                  },
                  t === home && { opacity: 0.3 },
                ]}
                activeOpacity={0.8}
              >
                <Text style={[
                  styles.choiceText,
                  away === t && t !== 'White' && { color: '#fff' },
                ]}>
                  {t.toUpperCase()}
                </Text>
              </TouchableOpacity>
            ))}
          </View>

          <Text style={[styles.label, { marginTop: spacing.md }]}>DATE</Text>
          <View style={styles.row}>
            {[0, 1, 2, 3, 4, 5, 6].map((n) => {
              const d = todayPlusDays(n);
              const short = n === 0
                ? 'Today'
                : d.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric' });
              return (
                <TouchableOpacity
                  key={n}
                  onPress={() => setDateOffset(n)}
                  style={[styles.choice, dateOffset === n && styles.choiceActive]}
                  activeOpacity={0.8}
                >
                  <Text style={[styles.choiceText, dateOffset === n && styles.choiceTextActive]}>
                    {short}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>

          <Text style={[styles.label, { marginTop: spacing.md }]}>KICK-OFF TIME (HH:MM)</Text>
          <TextInput
            testID="add-match-time-input"
            value={time}
            onChangeText={(v) => {
              const cleaned = v.replace(/[^\d:]/g, '').slice(0, 5);
              setTime(cleaned);
            }}
            placeholder="19:00"
            placeholderTextColor={colors.textMuted}
            style={[styles.input, { width: 120 }]}
            keyboardType="numbers-and-punctuation"
          />

          <TouchableOpacity
            testID="submit-add-match-btn"
            disabled={saving}
            onPress={submit}
            style={[styles.primaryBtn, saving && { opacity: 0.6 }]}
            activeOpacity={0.85}
          >
            {saving ? <ActivityIndicator color="#fff" /> : <Text style={styles.primaryBtnText}>ADD FIXTURE</Text>}
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  header: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.md,
    flexDirection: 'row',
    alignItems: 'flex-end',
  },
  createBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: colors.primary,
    paddingHorizontal: spacing.md,
    height: 40,
    borderRadius: radii.md,
    borderBottomWidth: 3,
    borderBottomColor: colors.primaryDark,
  },
  createBtnText: { color: '#fff', fontWeight: '900', letterSpacing: 1 },
  list: {
    paddingHorizontal: spacing.lg,
    paddingBottom: 220,
    gap: spacing.sm,
  },
  cardWrap: { marginBottom: spacing.sm },
  card: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.md,
    padding: spacing.md,
  },
  trophyIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.surfaceAccent,
    borderWidth: 1,
    borderColor: colors.border,
  },
  teamChipsRow: {
    marginTop: spacing.sm,
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
  },
  teamChip: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.sm,
    borderWidth: 1,
    backgroundColor: colors.background,
    gap: 6,
  },
  teamDot: { width: 8, height: 8, borderRadius: 4 },
  teamChipText: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  tag: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 4,
    borderWidth: 1,
  },
  tagText: { fontSize: 10, fontWeight: '900', letterSpacing: 1 },
  expanded: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderTopWidth: 0,
    borderColor: colors.border,
    borderBottomLeftRadius: radii.md,
    borderBottomRightRadius: radii.md,
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.md,
    marginTop: -spacing.sm,
    paddingTop: spacing.md,
  },
  tableHeader: {
    flexDirection: 'row',
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderColor: colors.border,
  },
  th: {
    flex: 1,
    color: colors.textSecondary,
    fontSize: 10,
    fontWeight: '900',
    letterSpacing: 1,
    textAlign: 'center',
  },
  tableRow: {
    flexDirection: 'row',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderColor: colors.border,
    alignItems: 'center',
  },
  tdTeam: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingLeft: 6,
  },
  td: {
    flex: 1,
    color: colors.textPrimary,
    fontSize: 12,
    fontWeight: '700',
    textAlign: 'center',
  },
  fixture: {
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
  fixturePlayed: { borderColor: colors.borderLight },
  fixtureLive: {
    borderColor: colors.danger,
    backgroundColor: '#3b1818',
  },
  liveBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 3,
    backgroundColor: colors.danger,
    marginTop: 2,
  },
  liveBadgeDot: {
    width: 5,
    height: 5,
    borderRadius: 2.5,
    backgroundColor: '#fff',
  },
  liveBadgeText: {
    color: '#fff',
    fontSize: 9,
    fontWeight: '900',
    letterSpacing: 1,
  },
  fixtureRoundCol: {
    width: 56,
    alignItems: 'center',
  },
  fixtureRound: {
    color: colors.primary,
    fontWeight: '900',
    fontSize: 14,
    letterSpacing: 1,
  },
  fixtureTeams: { flex: 1, gap: 3 },
  fixtureTeamRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  fixtureTeam: {
    flex: 1,
    color: colors.textPrimary,
    fontSize: 13,
    fontWeight: '700',
  },
  fixtureScore: {
    color: colors.textPrimary,
    fontSize: 16,
    fontWeight: '900',
    minWidth: 24,
    textAlign: 'right',
  },
  dangerBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    marginTop: spacing.md,
    height: 40,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.danger,
  },
  dangerBtnText: {
    color: colors.danger,
    fontWeight: '900',
    letterSpacing: 1,
    fontSize: 12,
  },
  // Modal
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
    borderTopWidth: 1,
    borderColor: colors.border,
    maxHeight: '92%',
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
    height: 44,
    color: colors.textPrimary,
    fontSize: 15,
  },
  row: { flexDirection: 'row', gap: spacing.sm, flexWrap: 'wrap', marginTop: 6 },
  choice: {
    paddingHorizontal: spacing.md,
    height: 36,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.background,
  },
  choiceActive: { backgroundColor: colors.primary, borderColor: colors.primary },
  choiceText: { color: colors.textSecondary, fontWeight: '800', letterSpacing: 0.5 },
  choiceTextActive: { color: '#fff' },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: spacing.md,
    marginBottom: spacing.sm,
  },
  miniBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 8,
    height: 26,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: colors.primary,
  },
  miniBtnText: {
    color: colors.primary,
    fontSize: 10,
    fontWeight: '900',
    letterSpacing: 1,
  },
  teamRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: 8,
  },
  teamColorSwatch: {
    width: 14,
    height: 14,
    borderRadius: 7,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  iconBtn: {
    width: 36,
    height: 36,
    borderRadius: radii.md,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: colors.border,
  },
  playerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderColor: colors.border,
  },
  playerName: {
    color: colors.textPrimary,
    fontSize: 14,
    fontWeight: '700',
  },
  assignChip: {
    paddingHorizontal: 10,
    height: 30,
    borderRadius: radii.sm,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
    minWidth: 100,
  },
  assignChipText: {
    color: colors.textPrimary,
    fontSize: 11,
    fontWeight: '900',
    letterSpacing: 1,
  },
  primaryBtn: {
    marginTop: spacing.lg,
    backgroundColor: colors.primary,
    height: 54,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radii.md,
    borderBottomWidth: 4,
    borderBottomColor: colors.primaryDark,
  },
  primaryBtnText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '900',
    letterSpacing: 1,
  },
  toggleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.sm,
    gap: spacing.md,
  },
  toggleLabel: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 1.5,
    marginBottom: 2,
  },
  toggle: {
    width: 44,
    height: 26,
    borderRadius: 13,
    backgroundColor: colors.surfaceAccent,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 2,
    justifyContent: 'center',
  },
  toggleOn: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  toggleKnob: {
    width: 20,
    height: 20,
    borderRadius: 10,
    backgroundColor: colors.textMuted,
  },
  toggleKnobOn: {
    backgroundColor: '#fff',
    transform: [{ translateX: 18 }],
  },
});
