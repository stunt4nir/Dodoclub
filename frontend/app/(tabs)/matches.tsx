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
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useFocusEffect, useRouter } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { api } from '../../src/api';
import { colors, spacing, radii } from '../../src/theme';
import { Display, Overline, Muted, Title } from '../../src/typography';

type Match = {
  id: string;
  title: string;
  date: string;
  location?: string | null;
  team_size: number;
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

export default function MatchesScreen() {
  const router = useRouter();
  const [matches, setMatches] = useState<Match[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  // form state
  const [title, setTitle] = useState('');
  const [location, setLocation] = useState('');
  const [teamSize, setTeamSize] = useState('5');
  const [whenDays, setWhenDays] = useState(3);
  const [whenHour, setWhenHour] = useState(19);

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
    setWhenDays(3);
    setWhenHour(19);
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
    setSaving(true);
    try {
      const d = new Date();
      d.setDate(d.getDate() + whenDays);
      d.setHours(whenHour, 0, 0, 0);
      await api('/matches', {
        method: 'POST',
        body: {
          title: title.trim(),
          location: location.trim() || null,
          date: d.toISOString(),
          team_size: ts,
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
              <Text style={styles.cardMeta}>
                {item.team_size}v{item.team_size} ·{' '}
                {item.votes.filter((v: any) => v.vote === 'yes').length} IN /{' '}
                {item.votes.filter((v: any) => v.vote === 'reserve').length} RES /{' '}
                {item.votes.filter((v: any) => v.vote === 'no').length} OUT
              </Text>
              {item.result && (
                <Text style={styles.scoreText}>
                  {item.result.team_a_score} – {item.result.team_b_score}
                </Text>
              )}
            </View>
          </TouchableOpacity>
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

            <Text style={[styles.label, { marginTop: spacing.md }]}>TEAM SIZE</Text>
            <View style={styles.row}>
              {[3, 5, 7, 11].map((n) => (
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

            <Text style={[styles.label, { marginTop: spacing.md }]}>WHEN (DAYS FROM NOW)</Text>
            <View style={styles.row}>
              {[1, 3, 7, 14].map((n) => (
                <TouchableOpacity
                  key={n}
                  testID={`when-days-${n}-btn`}
                  onPress={() => setWhenDays(n)}
                  style={[styles.choice, whenDays === n && styles.choiceActive]}
                  activeOpacity={0.8}
                >
                  <Text
                    style={[
                      styles.choiceText,
                      whenDays === n && styles.choiceTextActive,
                    ]}
                  >
                    {n}d
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            <Text style={[styles.label, { marginTop: spacing.md }]}>KICK-OFF HOUR</Text>
            <View style={styles.row}>
              {[17, 18, 19, 20, 21].map((h) => (
                <TouchableOpacity
                  key={h}
                  testID={`hour-${h}-btn`}
                  onPress={() => setWhenHour(h)}
                  style={[styles.choice, whenHour === h && styles.choiceActive]}
                  activeOpacity={0.8}
                >
                  <Text
                    style={[
                      styles.choiceText,
                      whenHour === h && styles.choiceTextActive,
                    ]}
                  >
                    {h}:00
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
  },
  cardMeta: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 0.8,
  },
  scoreText: {
    color: colors.textPrimary,
    fontWeight: '900',
    fontSize: 16,
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
  row: { flexDirection: 'row', gap: spacing.sm, flexWrap: 'wrap' },
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
