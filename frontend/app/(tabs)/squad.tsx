import React, { useCallback, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useFocusEffect } from 'expo-router';
import { api } from '../../src/api';
import { colors, spacing, radii } from '../../src/theme';
import { Display, Overline, Muted } from '../../src/typography';
import Avatar from '../../src/Avatar';

type Player = {
  id: string;
  name: string;
  shirt_number: number | null;
  profile_picture: string | null;
  goals: number;
  assists: number;
  matches_played: number;
  rating: number;
  role: string;
  can_edit_matches: boolean;
};

export default function SquadScreen() {
  const [players, setPlayers] = useState<Player[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

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
        <Overline>Leaderboard</Overline>
        <Display style={{ fontSize: 32, lineHeight: 34 }}>The Squad</Display>
        <Muted style={{ marginTop: 4 }}>
          Ranked by form · Rating = Goals×3 + Assists×2 + Matches
        </Muted>
      </View>

      <FlatList
        data={players}
        keyExtractor={(p) => p.id}
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
              <Text style={styles.name} numberOfLines={1}>
                {item.name}
                {item.role === 'admin' && (
                  <Text style={styles.adminTag}>  ADMIN</Text>
                )}
              </Text>
              <Text style={styles.meta}>
                {item.goals}G · {item.assists}A · {item.matches_played} MP
              </Text>
            </View>
            <View style={styles.ratingPill}>
              <Text style={styles.ratingValue}>{item.rating}</Text>
              <Text style={styles.ratingLabel}>RATING</Text>
            </View>
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
    paddingBottom: spacing.md,
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
    fontSize: 10,
    letterSpacing: 1.2,
  },
  ratingPill: {
    alignItems: 'center',
    minWidth: 60,
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
});
