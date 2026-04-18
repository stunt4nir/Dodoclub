import React, { useCallback, useState } from 'react';
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
import { colors, spacing, radii } from '../../src/theme';
import { Display, Overline, Muted, Title } from '../../src/typography';

type Match = {
  id: string;
  title: string;
  date: string;
  location?: string | null;
  team_size: number;
  match_type: 'friendly' | 'league';
  third_team_enabled: boolean;
  status: 'voting' | 'scheduled' | 'played';
  votes: any[];
  result?: any;
};

function formatDate(d: string) {
  const dt = new Date(d);
  if (isNaN(dt.getTime())) return d;
  return dt.toLocaleString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function StatusPill({ status }: { status: Match['status'] }) {
  const map = {
    voting: { label: 'VOTING', color: colors.warning },
    scheduled: { label: 'SCHEDULED', color: colors.primary },
    played: { label: 'PLAYED', color: colors.success },
  };
  const v = map[status];
  return (
    <View style={[styles.statusPill, { borderColor: v.color }]}>
      <Text style={[styles.statusText, { color: v.color }]}>{v.label}</Text>
    </View>
  );
}

function todayPlusDays(d: number): Date {
  const out = new Date();
  out.setDate(out.getDate() + d);
  return out;
}

export default function MatchesScreen() {
  const router = useRouter();
  const { user } = useAuth();
  const [matches, setMatches] = useState<Match[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  // form state
  const [title, setTitle] = useState('');
  const [location, setLocation] = useState('');
  const [teamSize, setTeamSize] = useState('5');
  const [matchType, setMatchType] = useState<'friendly' | 'league'>('friendly');
  const [thirdTeam, setThirdTeam] = useState(false);
  const [dateOffset, setDateOffset] = useState(3); // days
  const [hour, setHour] = useState('19');
  const [minute, setMinute] = useState('00');
  const [duration, setDuration] = useState(60);

  const canEdit = !!user && (user.role === 'admin' || user.can_edit_matches);

  const load = useCallback(async () => {
    try {
      const data = await api<Match[]>('/matches');
      setMatches(data);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  const resetForm = () => {
    setTitle('');
    setLocation('');
    setTeamSize('5');
    setMatchType('friendly');
    setThirdTeam(false);
    setDateOffset(3);
    setHour('19');
    setMinute('00');
    setDuration(60);
  };

  const createMatch = async () => {
    if (!title.trim()) {
      Alert.alert('Missing title', 'Give the match a title.');
      return;
    }
    const ts = parseInt(teamSize, 10);
    if (!Number.isFinite(ts) || ts < 3 || ts > 11) {
      Alert.alert('Invalid team size', 'Choose between 3 and 11.');
      return;
    }
    const h = parseInt(hour, 10);
    const mn = parseInt(minute, 10);
    if (!Number.isFinite(h) || h < 0 || h > 23) {
      Alert.alert('Invalid hour', 'Hour must be 0-23.');
      return;
    }
    if (!Number.isFinite(mn) || mn < 0 || mn > 59) {
      Alert.alert('Invalid minutes', 'Minutes must be 0-59.');
      return;
    }
    if (matchType === 'league' && thirdTeam) {
      Alert.alert('Invalid combo', 'Third team is only available for friendly matches.');
      return;
    }
    setSaving(true);
    try {
      const d = todayPlusDays(dateOffset);
      d.setHours(h, mn, 0, 0);
      await api('/matches', {
        method: 'POST',
        body: {
          title: title.trim(),
          location: location.trim() || null,
          date: d.toISOString(),
          team_size: ts,
          match_type: matchType,
          third_team_enabled: thirdTeam,
          duration_minutes: duration,
        },
      });
      resetForm();
      setModalOpen(false);
      await load();
    } catch (e: any) {
      Alert.alert('Error', e.message || 'Failed to create match');
    } finally {
      setSaving(false);
    }
  };

  const deleteMatch = (mid: string, title: string) => {
    Alert.alert(
      `Delete "${title}"?`,
      'This reverts any stats recorded from this match.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              await api(`/matches/${mid}`, { method: 'DELETE' });
              await load();
            } catch (e: any) {
              Alert.alert('Error', e.message || 'Failed');
            }
          },
        },
      ]
    );
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.safe}>
        <ActivityIndicator color={colors.primary} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <View style={styles.header}>
        <View style={{ flex: 1 }}>
          <Overline>Fixtures</Overline>
          <Display style={{ fontSize: 32, lineHeight: 34 }}>Matches</Display>
        </View>
        <TouchableOpacity
          testID="open-create-match-modal"
          onPress={() => setModalOpen(true)}
          style={styles.createBtn}
          activeOpacity={0.85}
        >
          <Ionicons name="add" size={22} color="#fff" />
          <Text style={styles.createBtnText}>NEW</Text>
        </TouchableOpacity>
      </View>

      <FlatList
        data={matches}
        keyExtractor={(m) => m.id}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => {
              setRefreshing(true);
              load();
            }}
            tintColor={colors.primary}
          />
        }
        renderItem={({ item }) => (
          <View style={styles.cardWrap}>
            <TouchableOpacity
              testID={`match-card-${item.id}`}
              activeOpacity={0.85}
              onPress={() => router.push(`/match/${item.id}`)}
              style={styles.card}
            >
              <View style={styles.cardTop}>
                <Title style={{ fontSize: 18, flex: 1 }} numberOfLines={1}>
                  {item.title}
                </Title>
                <StatusPill status={item.status} />
              </View>
              <Muted style={{ marginTop: 6 }}>
                {formatDate(item.date)}
                {item.location ? ` · ${item.location}` : ''}
              </Muted>
              <View style={styles.cardFooter}>
                <View style={{ flexDirection: 'row', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
                  <View style={styles.tag}>
                    <Text style={styles.tagText}>
                      {item.team_size}v{item.team_size}
                      {item.third_team_enabled ? 'v' + item.team_size : ''}
                    </Text>
                  </View>
                  {item.match_type === 'league' && (
                    <View style={[styles.tag, { borderColor: colors.primary }]}>
                      <Text style={[styles.tagText, { color: colors.primary }]}>LEAGUE</Text>
                    </View>
                  )}
                  <Text style={styles.cardMeta}>
                    {item.votes.filter((v: any) => v.vote === 'yes').length}✓ /{' '}
                    {item.votes.filter((v: any) => v.vote === 'reserve').length}⟳ /{' '}
                    {item.votes.filter((v: any) => v.vote === 'no').length}✗
                  </Text>
                </View>
                {item.result && (
                  <Text style={styles.scoreText}>
                    {item.result.team_a_score} – {item.result.team_b_score}
                    {item.result.team_c_score != null ? ` – ${item.result.team_c_score}` : ''}
                  </Text>
                )}
              </View>
            </TouchableOpacity>
            {canEdit && (
              <TouchableOpacity
                testID={`match-delete-${item.id}`}
                onPress={() => deleteMatch(item.id, item.title)}
                style={styles.delBtn}
                hitSlop={8}
              >
                <Ionicons name="trash-outline" size={16} color={colors.danger} />
              </TouchableOpacity>
            )}
          </View>
        )}
        ListEmptyComponent={
          <Muted style={{ textAlign: 'center', marginTop: 40 }}>
            No matches yet — tap NEW to create one.
          </Muted>
        }
      />

      <Modal
        visible={modalOpen}
        transparent
        animationType="slide"
        onRequestClose={() => setModalOpen(false)}
      >
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={styles.modalBg}
        >
          <View style={styles.modalCard}>
            <ScrollView showsVerticalScrollIndicator={false}>
              <View style={styles.modalHeader}>
                <Title style={{ fontSize: 20 }}>New Match</Title>
                <TouchableOpacity
                  testID="close-create-match-modal"
                  onPress={() => setModalOpen(false)}
                  hitSlop={12}
                >
                  <Ionicons name="close" size={24} color={colors.textSecondary} />
                </TouchableOpacity>
              </View>

              <Text style={styles.label}>TITLE</Text>
              <TextInput
                testID="create-match-title-input"
                value={title}
                onChangeText={setTitle}
                placeholder="Friday night 5-a-side"
                placeholderTextColor={colors.textMuted}
                style={styles.input}
              />

              <Text style={[styles.label, { marginTop: spacing.md }]}>LOCATION (optional)</Text>
              <TextInput
                testID="create-match-location-input"
                value={location}
                onChangeText={setLocation}
                placeholder="PowerLeague Shoreditch"
                placeholderTextColor={colors.textMuted}
                style={styles.input}
              />

              <Text style={[styles.label, { marginTop: spacing.md }]}>MATCH TYPE</Text>
              <View style={styles.row}>
                {(['friendly', 'league'] as const).map((t) => (
                  <TouchableOpacity
                    key={t}
                    testID={`match-type-${t}-btn`}
                    onPress={() => {
                      setMatchType(t);
                      if (t === 'league') setThirdTeam(false);
                    }}
                    style={[styles.choice, matchType === t && styles.choiceActive]}
                    activeOpacity={0.8}
                  >
                    <Text
                      style={[
                        styles.choiceText,
                        matchType === t && styles.choiceTextActive,
                      ]}
                    >
                      {t.toUpperCase()}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
              <Muted style={{ fontSize: 11, marginTop: 4 }}>
                {matchType === 'league'
                  ? 'Win = 3 pts · Draw = 1 pt · Loss = 0 pts'
                  : 'Casual friendly — no league points awarded'}
              </Muted>

              <Text style={[styles.label, { marginTop: spacing.md }]}>TEAM SIZE</Text>
              <View style={styles.row}>
                {[3, 5, 6, 7, 8, 9, 11].map((n) => (
                  <TouchableOpacity
                    key={n}
                    testID={`team-size-${n}-btn`}
                    onPress={() => setTeamSize(String(n))}
                    style={[
                      styles.choice,
                      parseInt(teamSize, 10) === n && styles.choiceActive,
                    ]}
                    activeOpacity={0.8}
                  >
                    <Text
                      style={[
                        styles.choiceText,
                        parseInt(teamSize, 10) === n && styles.choiceTextActive,
                      ]}
                    >
                      {n}v{n}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>

              {matchType === 'friendly' && (
                <>
                  <Text style={[styles.label, { marginTop: spacing.md }]}>
                    THIRD TEAM (WHITE)
                  </Text>
                  <View style={styles.row}>
                    {[
                      { v: false, label: '2 TEAMS' },
                      { v: true, label: '3 TEAMS' },
                    ].map((opt) => (
                      <TouchableOpacity
                        key={opt.label}
                        testID={`third-team-${opt.v}-btn`}
                        onPress={() => setThirdTeam(opt.v)}
                        style={[styles.choice, thirdTeam === opt.v && styles.choiceActive]}
                        activeOpacity={0.8}
                      >
                        <Text
                          style={[
                            styles.choiceText,
                            thirdTeam === opt.v && styles.choiceTextActive,
                          ]}
                        >
                          {opt.label}
                        </Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </>
              )}

              <Text style={[styles.label, { marginTop: spacing.md }]}>DATE</Text>
              <View style={styles.row}>
                {[0, 1, 2, 3, 5, 7, 14].map((n) => {
                  const d = todayPlusDays(n);
                  const short = n === 0 ? 'Today' : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
                  return (
                    <TouchableOpacity
                      key={n}
                      testID={`date-offset-${n}-btn`}
                      onPress={() => setDateOffset(n)}
                      style={[styles.choice, dateOffset === n && styles.choiceActive]}
                      activeOpacity={0.8}
                    >
                      <Text
                        style={[
                          styles.choiceText,
                          dateOffset === n && styles.choiceTextActive,
                        ]}
                      >
                        {short}
                      </Text>
                    </TouchableOpacity>
                  );
                })}
              </View>

              <Text style={[styles.label, { marginTop: spacing.md }]}>EXACT KICK-OFF</Text>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <TextInput
                  testID="kickoff-hour-input"
                  value={hour}
                  onChangeText={(t) => setHour(t.replace(/[^0-9]/g, '').slice(0, 2))}
                  keyboardType="number-pad"
                  placeholder="HH"
                  placeholderTextColor={colors.textMuted}
                  style={[styles.input, styles.timeInput]}
                />
                <Text style={styles.timeSep}>:</Text>
                <TextInput
                  testID="kickoff-minute-input"
                  value={minute}
                  onChangeText={(t) => setMinute(t.replace(/[^0-9]/g, '').slice(0, 2))}
                  keyboardType="number-pad"
                  placeholder="MM"
                  placeholderTextColor={colors.textMuted}
                  style={[styles.input, styles.timeInput]}
                />
                <View style={{ flex: 1 }}>
                  <Muted style={{ fontSize: 11 }}>
                    {(() => {
                      const d = todayPlusDays(dateOffset);
                      const h = parseInt(hour || '0', 10);
                      const m = parseInt(minute || '0', 10);
                      if (!Number.isFinite(h) || !Number.isFinite(m)) return '';
                      d.setHours(h, m, 0, 0);
                      return d.toLocaleString(undefined, {
                        weekday: 'short',
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      });
                    })()}
                  </Muted>
                </View>
              </View>

              <View style={styles.row}>
                {['15', '30', '45', '00'].map((m) => (
                  <TouchableOpacity
                    key={m}
                    testID={`quick-minute-${m}-btn`}
                    onPress={() => setMinute(m)}
                    style={[styles.choice, minute === m && styles.choiceActive]}
                    activeOpacity={0.8}
                  >
                    <Text
                      style={[
                        styles.choiceText,
                        minute === m && styles.choiceTextActive,
                      ]}
                    >
                      :{m}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>

              <Text style={[styles.label, { marginTop: spacing.md }]}>MATCH DURATION</Text>
              <View style={styles.row}>
                {[30, 45, 60, 75, 90].map((n) => (
                  <TouchableOpacity
                    key={n}
                    testID={`duration-${n}-btn`}
                    onPress={() => setDuration(n)}
                    style={[styles.choice, duration === n && styles.choiceActive]}
                    activeOpacity={0.8}
                  >
                    <Text
                      style={[
                        styles.choiceText,
                        duration === n && styles.choiceTextActive,
                      ]}
                    >
                      {n} min
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>

              <TouchableOpacity
                testID="submit-create-match-btn"
                disabled={saving}
                onPress={createMatch}
                style={[styles.primaryBtn, saving && { opacity: 0.6 }]}
                activeOpacity={0.85}
              >
                {saving ? (
                  <ActivityIndicator color="#fff" />
                ) : (
                  <Text style={styles.primaryBtnText}>CREATE MATCH</Text>
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
  createBtnText: {
    color: '#fff',
    fontWeight: '900',
    letterSpacing: 1,
  },
  list: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.xxl,
    gap: spacing.sm,
  },
  cardWrap: { position: 'relative' },
  card: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.md,
    padding: spacing.md,
  },
  cardTop: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  cardFooter: {
    marginTop: spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 6,
  },
  tag: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: colors.borderLight,
    backgroundColor: colors.background,
  },
  tagText: {
    color: colors.textSecondary,
    fontSize: 10,
    fontWeight: '900',
    letterSpacing: 1,
  },
  cardMeta: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  scoreText: {
    color: colors.textPrimary,
    fontWeight: '900',
    fontSize: 15,
  },
  delBtn: {
    position: 'absolute',
    top: 8,
    right: 8,
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background,
    borderWidth: 1,
    borderColor: colors.border,
  },
  statusPill: {
    borderWidth: 1,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 4,
  },
  statusText: {
    fontSize: 10,
    fontWeight: '900',
    letterSpacing: 1.2,
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
    borderTopWidth: 1,
    borderColor: colors.border,
    maxHeight: '90%',
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
  timeInput: {
    width: 64,
    textAlign: 'center',
    fontSize: 20,
    fontWeight: '900',
  },
  timeSep: {
    color: colors.textPrimary,
    fontSize: 22,
    fontWeight: '900',
  },
  row: { flexDirection: 'row', gap: spacing.sm, flexWrap: 'wrap', marginTop: 6 },
  choice: {
    paddingHorizontal: spacing.md,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.background,
  },
  choiceActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  choiceText: {
    color: colors.textSecondary,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  choiceTextActive: { color: '#fff' },
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
});
