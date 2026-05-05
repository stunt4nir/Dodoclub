import React, { useCallback, useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  Image,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useFocusEffect } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { api } from '../../src/api';
import { useAuth } from '../../src/auth';
import { colors, spacing, radii } from '../../src/theme';
import { Display, Overline, Muted, Title } from '../../src/typography';

type ClubCfg = { club_name: string; club_logo: string | null };

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
  status: 'voting' | 'scheduled' | 'in_progress' | 'played';
  votes: Vote[];
  lineup?: any;
  result?: any;
  score_a?: number;
  score_b?: number;
  score_c?: number;
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

export default function HomeScreen() {
  const router = useRouter();
  const { user } = useAuth();
  const [cfg, setCfg] = useState<ClubCfg | null>(null);
  const [matches, setMatches] = useState<Match[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [voting, setVoting] = useState(false);

  const load = useCallback(async () => {
    try {
      const [c, m] = await Promise.all([
        api<ClubCfg>('/config', { auth: false }),
        api<Match[]>('/matches'),
      ]);
      setCfg(c);
      setMatches(m);
    } catch (e) {
      // ignore
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

  useEffect(() => {
    load();
  }, [load]);

  const upcoming =
    matches.find((m) => m.status === 'in_progress') ||
    matches.find((m) => m.status === 'voting') ||
    matches.find((m) => m.status === 'scheduled');

  const myVote = upcoming?.votes.find((v) => v.user_id === user?.id)?.vote;
  const counts = {
    yes: upcoming?.votes.filter((v) => v.vote === 'yes').length || 0,
    no: upcoming?.votes.filter((v) => v.vote === 'no').length || 0,
    reserve: upcoming?.votes.filter((v) => v.vote === 'reserve').length || 0,
  };

  const vote = async (v: 'yes' | 'no' | 'reserve') => {
    if (!upcoming || voting) return;
    setVoting(true);
    try {
      const updated = await api<Match>(`/matches/${upcoming.id}/vote`, {
        method: 'POST',
        body: { vote: v },
      });
      setMatches((prev) => prev.map((m) => (m.id === updated.id ? updated : m)));
    } catch {
      /* ignore */
    } finally {
      setVoting(false);
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
      <ScrollView
        contentContainerStyle={styles.scroll}
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
      >
        {/* Header */}
        <View style={styles.header}>
          <View style={styles.logoWrap}>
            {cfg?.club_logo ? (
              <Image source={{ uri: cfg.club_logo }} style={styles.logoImg} />
            ) : (
              <View style={styles.logoFallback}>
                <Text style={styles.logoLetter}>
                  {(cfg?.club_name || 'Club Dodo').slice(0, 1).toUpperCase()}
                </Text>
              </View>
            )}
          </View>
          <View style={{ flex: 1 }}>
            <Overline>Welcome, {user?.name}</Overline>
            <Display numberOfLines={1} style={{ fontSize: 32, lineHeight: 34 }}>
              {cfg?.club_name || 'Club Dodo'}
            </Display>
          </View>
        </View>

        {/* Quick stats */}
        <View style={styles.quickRow}>
          <View style={styles.quickCard}>
            <Text style={styles.quickValue}>{user?.goals ?? 0}</Text>
            <Text style={styles.quickLabel}>GOALS</Text>
          </View>
          <View style={styles.quickCard}>
            <Text style={styles.quickValue}>{user?.assists ?? 0}</Text>
            <Text style={styles.quickLabel}>ASSISTS</Text>
          </View>
          <View style={styles.quickCard}>
            <Text style={styles.quickValue}>{user?.matches_played ?? 0}</Text>
            <Text style={styles.quickLabel}>MATCHES</Text>
          </View>
          <View style={[styles.quickCard, styles.quickAccent]}>
            <Text style={[styles.quickValue, { color: colors.primary }]}>
              {user?.rating ?? 0}
            </Text>
            <Text style={styles.quickLabel}>RATING</Text>
          </View>
        </View>

        {/* Upcoming match */}
        <Overline style={{ marginTop: spacing.lg, marginBottom: spacing.sm }}>
          Next match
        </Overline>

        {!upcoming ? (
          <View style={styles.emptyCard}>
            <Ionicons name="calendar-outline" size={40} color={colors.textMuted} />
            <Title style={{ marginTop: spacing.md }}>No match scheduled</Title>
            <Muted style={{ marginTop: 6, textAlign: 'center' }}>
              Create the next Club Dodo fixture and start voting.
            </Muted>
            <TouchableOpacity
              testID="home-create-match-btn"
              style={styles.primaryBtn}
              onPress={() => router.push('/(tabs)/matches')}
            >
              <Text style={styles.primaryBtnText}>CREATE MATCH</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <TouchableOpacity
            activeOpacity={0.9}
            testID="home-upcoming-match-card"
            onPress={() => router.push(`/match/${upcoming.id}`)}
            style={styles.matchCard}
          >
            <View style={styles.matchHeader}>
              <View>
                <Overline>{upcoming.status.toUpperCase()}</Overline>
                <Title style={{ marginTop: 4 }} numberOfLines={1}>
                  {upcoming.title}
                </Title>
                <Muted style={{ marginTop: 4 }}>
                  {formatDate(upcoming.date)}
                  {upcoming.location ? ` · ${upcoming.location}` : ''}
                </Muted>
              </View>
              <View style={styles.sizeBadge}>
                <Text style={styles.sizeBadgeText}>{upcoming.team_size}v{upcoming.team_size}</Text>
              </View>
            </View>

            <View style={styles.voteRow}>
              <TouchableOpacity
                testID="vote-yes-btn"
                disabled={voting}
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
                <Text style={styles.voteCount}>{counts.yes}</Text>
              </TouchableOpacity>

              <TouchableOpacity
                testID="vote-reserve-btn"
                disabled={voting}
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
                <Text style={styles.voteCount}>{counts.reserve}</Text>
              </TouchableOpacity>

              <TouchableOpacity
                testID="vote-no-btn"
                disabled={voting}
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
                <Text style={styles.voteCount}>{counts.no}</Text>
              </TouchableOpacity>
            </View>

            <View style={styles.seeDetail}>
              <Text style={styles.seeDetailText}>Tap to see lineup & details</Text>
              <Ionicons name="chevron-forward" size={16} color={colors.textSecondary} />
            </View>
          </TouchableOpacity>
        )}

        <Overline style={{ marginTop: spacing.lg, marginBottom: spacing.sm }}>
          Recent matches
        </Overline>
        {matches.filter((m) => m.status === 'played').slice(0, 3).map((m) => (
          <TouchableOpacity
            key={m.id}
            testID={`recent-match-${m.id}`}
            activeOpacity={0.85}
            onPress={() => router.push(`/match/${m.id}`)}
            style={styles.recentCard}
          >
            <View style={{ flex: 1 }}>
              <Title numberOfLines={1} style={{ fontSize: 16 }}>{m.title}</Title>
              <Muted style={{ marginTop: 2 }}>{formatDate(m.date)}</Muted>
            </View>
            {m.result && (
              <View style={styles.scoreBadge}>
                <Text style={styles.scoreText}>
                  {m.result.team_a_score} – {m.result.team_b_score}
                </Text>
              </View>
            )}
          </TouchableOpacity>
        ))}
        {matches.filter((m) => m.status === 'played').length === 0 && (
          <Muted>No past matches yet.</Muted>
        )}
      </ScrollView>
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
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    marginBottom: spacing.lg,
  },
  logoWrap: {
    width: 56,
    height: 56,
    borderRadius: 28,
    overflow: 'hidden',
    borderWidth: 2,
    borderColor: colors.primary,
  },
  logoImg: { width: '100%', height: '100%' },
  logoFallback: {
    flex: 1,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  logoLetter: {
    color: '#fff',
    fontSize: 26,
    fontWeight: '900',
  },
  quickRow: { flexDirection: 'row', gap: spacing.sm },
  quickCard: {
    flex: 1,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.md,
    paddingVertical: spacing.md,
    alignItems: 'center',
  },
  quickAccent: { borderColor: colors.primary },
  quickValue: {
    color: colors.textPrimary,
    fontSize: 22,
    fontWeight: '900',
  },
  quickLabel: {
    color: colors.textSecondary,
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 1.2,
    marginTop: 2,
  },
  matchCard: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.lg,
    padding: spacing.md,
  },
  matchHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: spacing.md,
  },
  sizeBadge: {
    backgroundColor: colors.surfaceAccent,
    borderWidth: 1,
    borderColor: colors.border,
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    borderRadius: radii.sm,
  },
  sizeBadgeText: {
    color: colors.textPrimary,
    fontSize: 12,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
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
  voteLabel: {
    fontSize: 13,
    fontWeight: '900',
    letterSpacing: 1,
  },
  voteCount: {
    color: colors.textPrimary,
    fontSize: 18,
    fontWeight: '800',
  },
  seeDetail: {
    marginTop: spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 4,
  },
  seeDetailText: {
    color: colors.textSecondary,
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  emptyCard: {
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    padding: spacing.xl,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.border,
    borderStyle: 'dashed',
  },
  primaryBtn: {
    marginTop: spacing.lg,
    backgroundColor: colors.primary,
    paddingHorizontal: spacing.lg,
    height: 46,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radii.md,
    borderBottomWidth: 3,
    borderBottomColor: colors.primaryDark,
  },
  primaryBtnText: {
    color: '#fff',
    fontSize: 14,
    fontWeight: '900',
    letterSpacing: 1,
  },
  recentCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.md,
    padding: spacing.md,
    marginBottom: spacing.sm,
  },
  scoreBadge: {
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
    backgroundColor: colors.surfaceAccent,
    borderRadius: radii.sm,
  },
  scoreText: {
    color: colors.textPrimary,
    fontWeight: '900',
    fontSize: 16,
  },
});
