import React, { useCallback, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useFocusEffect } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { api } from '../../src/api';
import { useAuth } from '../../src/auth';
import { colors, spacing, radii } from '../../src/theme';
import { Display, Overline, Muted } from '../../src/typography';
import Avatar from '../../src/Avatar';

type Player = {
  id: string;
  name: string;
  shirt_number: number | null;
  profile_picture: string | null;
  preferred_position: string | null;
  preferred_positions?: string[];
  goals: number;
  assists: number;
  matches_played: number;
  wins: number;
  draws: number;
  losses: number;
  league_points: number;
  rating: number;
  role: string;
  can_edit_matches: boolean;
};

type Tab = 'rating' | 'league';

export default function SquadScreen() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const [players, setPlayers] = useState<Player[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [tab, setTab] = useState<Tab>('rating');
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await api<Player[]>('/users');
      setPlayers(data);
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

  const confirmDeletePlayer = useCallback((p: Player) => {
    Alert.alert(
      'Delete player?',
      `This will permanently remove ${p.name} from the squad, wipe their votes, lineup slots, and chat messages. This cannot be undone.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            setDeletingId(p.id);
            try {
              await api(`/users/${p.id}`, { method: 'DELETE' });
              setPlayers((prev) => prev.filter((x) => x.id !== p.id));
            } catch (e: any) {
              Alert.alert('Error', e.message || 'Delete failed');
            } finally {
              setDeletingId(null);
            }
          },
        },
      ],
    );
  }, []);

  if (loading) {
    return (
      <SafeAreaView style={styles.safe}>
        <ActivityIndicator color={colors.primary} />
      </SafeAreaView>
    );
  }

  const sorted = [...players].sort((a, b) => {
    if (tab === 'league') {
      if (b.league_points !== a.league_points) return b.league_points - a.league_points;
      return b.rating - a.rating;
    }
    return b.rating - a.rating;
  });

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <View style={styles.header}>
        <Overline>Leaderboard</Overline>
        <Display style={{ fontSize: 32, lineHeight: 34 }}>The Squad</Display>
      </View>

      <View style={styles.tabsRow}>
        <TouchableOpacity
          testID="tab-rating"
          onPress={() => setTab('rating')}
          activeOpacity={0.85}
          style={[styles.tab, tab === 'rating' && styles.tabActive]}
        >
          <Text style={[styles.tabText, tab === 'rating' && styles.tabTextActive]}>
            FORM
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          testID="tab-league"
          onPress={() => setTab('league')}
          activeOpacity={0.85}
          style={[styles.tab, tab === 'league' && styles.tabActive]}
        >
          <Text style={[styles.tabText, tab === 'league' && styles.tabTextActive]}>
            LEAGUE
          </Text>
        </TouchableOpacity>
      </View>

      {tab === 'league' && (
        <View style={styles.legend}>
          <Text style={styles.legendText}>W · D · L · PTS</Text>
        </View>
      )}

      <FlatList
        data={sorted}
        keyExtractor={(p) => p.id}
        contentContainerStyle={styles.list}
        initialNumToRender={12}
        maxToRenderPerBatch={10}
        windowSize={7}
        removeClippedSubviews
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
        renderItem={({ item, index }) => (
          <View style={styles.row} testID={`squad-player-${item.id}`}>
            <Text style={styles.rank}>{index + 1}</Text>
            <Avatar
              uri={item.profile_picture}
              size={48}
              shirt={item.shirt_number}
              name={item.name}
            />
            <View style={{ flex: 1, marginLeft: spacing.md }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                <Text style={styles.name} numberOfLines={1}>
                  {item.name}
                </Text>
                {(() => {
                  const posList = (item.preferred_positions && item.preferred_positions.length > 0)
                    ? item.preferred_positions
                    : (item.preferred_position ? [item.preferred_position] : []);
                  if (posList.length === 0) return null;
                  return (
                    <View style={styles.posBadge}>
                      <Text style={styles.posBadgeText}>{posList.slice(0, 2).join('/')}</Text>
                    </View>
                  );
                })()}
                {item.role === 'admin' && (
                  <Text style={styles.adminTag}>ADMIN</Text>
                )}
              </View>
              <Text style={styles.meta}>
                {tab === 'rating'
                  ? `${item.goals}G · ${item.assists}A · ${item.matches_played} MP`
                  : `${item.wins}W · ${item.draws}D · ${item.losses}L`}
              </Text>
            </View>
            <View style={styles.ratingPill}>
              <Text style={styles.ratingValue}>
                {tab === 'rating' ? item.rating : item.league_points}
              </Text>
              <Text style={styles.ratingLabel}>
                {tab === 'rating' ? 'RATING' : 'POINTS'}
              </Text>
            </View>
            {isAdmin && item.id !== user?.id && (
              <TouchableOpacity
                testID={`delete-player-${item.id}`}
                onPress={() => confirmDeletePlayer(item)}
                disabled={deletingId === item.id}
                activeOpacity={0.7}
                style={styles.deleteBtn}
                hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
              >
                {deletingId === item.id ? (
                  <ActivityIndicator color={colors.danger} size="small" />
                ) : (
                  <Ionicons name="trash-outline" size={18} color={colors.danger} />
                )}
              </TouchableOpacity>
            )}
          </View>
        )}
        ListEmptyComponent={
          <Muted style={{ textAlign: 'center', marginTop: 40 }}>
            No players yet.
          </Muted>
        }
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  header: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.sm,
  },
  tabsRow: {
    flexDirection: 'row',
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    marginBottom: spacing.sm,
  },
  tab: {
    flex: 1,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  tabActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  tabText: {
    color: colors.textSecondary,
    fontWeight: '900',
    letterSpacing: 1.2,
    fontSize: 12,
  },
  tabTextActive: { color: '#fff' },
  legend: {
    paddingHorizontal: spacing.lg,
    marginBottom: 6,
  },
  legendText: {
    color: colors.textMuted,
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 1.5,
    textAlign: 'right',
  },
  list: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.xxl,
    gap: spacing.sm,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.md,
    padding: spacing.md,
  },
  rank: {
    color: colors.primary,
    fontWeight: '900',
    fontSize: 18,
    width: 28,
  },
  name: {
    color: colors.textPrimary,
    fontSize: 16,
    fontWeight: '800',
    flexShrink: 1,
  },
  posBadge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    backgroundColor: colors.surfaceAccent,
    borderWidth: 1,
    borderColor: colors.borderLight,
  },
  posBadgeText: {
    color: colors.textSecondary,
    fontSize: 9,
    fontWeight: '900',
    letterSpacing: 1,
  },
  meta: {
    color: colors.textSecondary,
    fontSize: 12,
    marginTop: 2,
    fontWeight: '600',
    letterSpacing: 0.3,
  },
  adminTag: {
    color: colors.primary,
    fontWeight: '900',
    fontSize: 9,
    letterSpacing: 1.2,
    marginLeft: 4,
  },
  ratingPill: {
    alignItems: 'center',
    minWidth: 64,
    backgroundColor: colors.surfaceAccent,
    borderRadius: radii.sm,
    paddingVertical: 6,
    paddingHorizontal: spacing.sm,
  },
  ratingValue: {
    color: colors.primary,
    fontWeight: '900',
    fontSize: 18,
  },
  ratingLabel: {
    color: colors.textSecondary,
    fontSize: 9,
    fontWeight: '800',
    letterSpacing: 1,
  },
  deleteBtn: {
    marginLeft: spacing.sm,
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
});
