import React, { useCallback, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  TextInput,
  Image,
  Platform,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useFocusEffect, useRouter } from 'expo-router';
import * as ImagePicker from 'expo-image-picker';
import { Ionicons } from '@expo/vector-icons';
import { api } from '../../src/api';
import { useAuth, User } from '../../src/auth';
import { colors, spacing, radii } from '../../src/theme';
import { Display, Overline, Muted, Title } from '../../src/typography';
import Avatar from '../../src/Avatar';

type ClubCfg = { club_name: string; club_logo: string | null };

async function pickImage(): Promise<string | null> {
  const res = await ImagePicker.requestMediaLibraryPermissionsAsync();
  if (!res.granted) {
    Alert.alert('Permission needed', 'Enable photo access to upload a picture.');
    return null;
  }
  const pick = await ImagePicker.launchImageLibraryAsync({
    mediaTypes: ['images'],
    allowsEditing: true,
    aspect: [1, 1],
    quality: 0.4,
    base64: true,
  });
  if (pick.canceled) return null;
  const a = pick.assets[0];
  if (a.base64) return `data:image/jpeg;base64,${a.base64}`;
  return a.uri || null;
}

export default function ProfileScreen() {
  const { user, logout, refresh } = useAuth();
  const router = useRouter();
  const [cfg, setCfg] = useState<ClubCfg | null>(null);
  const [allUsers, setAllUsers] = useState<User[]>([]);
  const [name, setName] = useState(user?.name || '');
  const [shirt, setShirt] = useState(user?.shirt_number ? String(user.shirt_number) : '');
  const [position, setPosition] = useState<User['preferred_position']>(user?.preferred_position || null);
  const [pic, setPic] = useState<string | null>(user?.profile_picture || null);
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingClub, setSavingClub] = useState(false);
  const [clubName, setClubName] = useState('');
  const [clubLogo, setClubLogo] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [c, users] = await Promise.all([
        api<ClubCfg>('/config', { auth: false }),
        api<User[]>('/users'),
      ]);
      setCfg(c);
      setClubName(c.club_name);
      setClubLogo(c.club_logo);
      setAllUsers(users);
    } catch {
      /* ignore */
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
      if (user) {
        setName(user.name);
        setShirt(user.shirt_number ? String(user.shirt_number) : '');
        setPosition(user.preferred_position || null);
        setPic(user.profile_picture);
      }
    }, [load, user])
  );

  const saveProfile = async () => {
    setSavingProfile(true);
    try {
      const n = shirt ? parseInt(shirt, 10) : null;
      const body: any = { name: name.trim() };
      if (n != null && Number.isFinite(n)) body.shirt_number = n;
      if (position) body.preferred_position = position;
      if (pic !== user?.profile_picture) body.profile_picture = pic;
      await api('/users/me', { method: 'PUT', body });
      await refresh();
      Alert.alert('Saved', 'Your profile has been updated.');
    } catch (e: any) {
      Alert.alert('Error', e.message || 'Save failed');
    } finally {
      setSavingProfile(false);
    }
  };

  const pickProfilePic = async () => {
    const uri = await pickImage();
    if (uri) setPic(uri);
  };

  const pickClubLogo = async () => {
    const uri = await pickImage();
    if (uri) setClubLogo(uri);
  };

  const saveClub = async () => {
    setSavingClub(true);
    try {
      await api('/config', {
        method: 'PUT',
        body: { club_name: clubName.trim(), club_logo: clubLogo },
      });
      Alert.alert('Saved', 'Club identity updated.');
      await load();
    } catch (e: any) {
      Alert.alert('Error', e.message || 'Save failed');
    } finally {
      setSavingClub(false);
    }
  };

  const toggleEdit = async (uid: string, can: boolean) => {
    try {
      await api('/users/grant-edit', {
        method: 'POST',
        body: { user_id: uid, can_edit_matches: can },
      });
      await load();
    } catch (e: any) {
      Alert.alert('Error', e.message || 'Failed');
    }
  };

  const resetAppData = () => {
    Alert.alert(
      'Reset all app data?',
      'Deletes every match and every non-admin player, and zeros out admin stats. This cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Reset everything',
          style: 'destructive',
          onPress: async () => {
            try {
              const res = await api<{ matches_deleted: number; users_deleted: number }>(
                '/admin/reset',
                { method: 'POST' }
              );
              await refresh();
              await load();
              Alert.alert(
                'Reset complete',
                `Deleted ${res.matches_deleted} match(es) and ${res.users_deleted} player(s).`
              );
            } catch (e: any) {
              Alert.alert('Error', e.message || 'Reset failed');
            }
          },
        },
      ]
    );
  };

  const resetMatches = () => {
    Alert.alert(
      'Reset matches only?',
      'Deletes every match (fixtures + history + votes). Players and their career stats are preserved.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete matches',
          style: 'destructive',
          onPress: async () => {
            try {
              const res = await api<{ matches_deleted: number }>(
                '/admin/reset/matches',
                { method: 'POST' }
              );
              await load();
              Alert.alert('Done', `Deleted ${res.matches_deleted} match(es).`);
            } catch (e: any) {
              Alert.alert('Error', e.message || 'Failed');
            }
          },
        },
      ]
    );
  };

  const resetLeague = () => {
    Alert.alert(
      'Start a new season?',
      'Resets every player\'s W / D / L / League Points to 0. Goals, assists, matches played and match history are kept.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Reset standings',
          style: 'destructive',
          onPress: async () => {
            try {
              const res = await api<{ users_reset: number }>(
                '/admin/reset/league',
                { method: 'POST' }
              );
              await refresh();
              await load();
              Alert.alert('New season started', `Reset league standings for ${res.users_reset} player(s).`);
            } catch (e: any) {
              Alert.alert('Error', e.message || 'Failed');
            }
          },
        },
      ]
    );
  };

  if (!user) {
    return (
      <SafeAreaView style={styles.safe}>
        <ActivityIndicator color={colors.primary} />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.headerRow}>
          <View style={{ flex: 1 }}>
            <Overline>You</Overline>
            <Display style={{ fontSize: 32, lineHeight: 34 }}>Profile</Display>
          </View>
          <TouchableOpacity
            testID="logout-btn"
            onPress={async () => {
              await logout();
              router.replace('/(auth)/login');
            }}
            style={styles.logoutBtn}
          >
            <Ionicons name="log-out-outline" size={18} color={colors.textPrimary} />
            <Text style={styles.logoutText}>LOGOUT</Text>
          </TouchableOpacity>
        </View>

        <View style={styles.card}>
          <View style={styles.profileRow}>
            <TouchableOpacity
              testID="pick-profile-pic-btn"
              onPress={pickProfilePic}
              activeOpacity={0.8}
            >
              <Avatar uri={pic} name={name} shirt={shirt ? parseInt(shirt, 10) : undefined} size={92} />
              <View style={styles.editIcon}>
                <Ionicons name="camera" size={14} color="#fff" />
              </View>
            </TouchableOpacity>
            <View style={{ flex: 1, marginLeft: spacing.md }}>
              <Muted>{user.email}</Muted>
              <Text style={styles.roleTag}>{user.role === 'admin' ? 'ADMIN' : 'PLAYER'}</Text>
              <Text style={styles.statLine}>
                {user.goals}G · {user.assists}A · {user.matches_played}MP · Rating {user.rating}
              </Text>
            </View>
          </View>

          <Text style={styles.label}>NAME</Text>
          <TextInput
            testID="profile-name-input"
            value={name}
            onChangeText={setName}
            style={styles.input}
            placeholderTextColor={colors.textMuted}
          />

          <Text style={[styles.label, { marginTop: spacing.md }]}>SHIRT NUMBER</Text>
          <TextInput
            testID="profile-shirt-input"
            value={shirt}
            onChangeText={(t) => setShirt(t.replace(/[^0-9]/g, '').slice(0, 2))}
            keyboardType="number-pad"
            style={styles.input}
            placeholder="10"
            placeholderTextColor={colors.textMuted}
          />

          <Text style={[styles.label, { marginTop: spacing.md }]}>PREFERRED POSITION</Text>
          {([
            { group: 'Goalkeeper', items: ['GK'] },
            { group: 'Defenders', items: ['CB', 'LB', 'RB'] },
            { group: 'Midfielders', items: ['CDM', 'CM', 'CAM'] },
            { group: 'Attackers', items: ['LW', 'ST', 'RW'] },
            { group: 'Flexible', items: ['ANY'] },
          ] as const).map((section) => (
            <View key={section.group} style={{ marginTop: 8 }}>
              <Text style={styles.posGroupLabel}>{section.group}</Text>
              <View style={styles.chipRow}>
                {section.items.map((p) => (
                  <TouchableOpacity
                    key={p}
                    testID={`position-${p}-btn`}
                    onPress={() => setPosition(p as User['preferred_position'])}
                    activeOpacity={0.85}
                    style={[styles.posChip, position === p && styles.posChipActive]}
                  >
                    <Text style={[styles.posChipText, position === p && styles.posChipTextActive]}>
                      {p}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>
          ))}

          <TouchableOpacity
            testID="save-profile-btn"
            onPress={saveProfile}
            disabled={savingProfile}
            style={[styles.primaryBtn, savingProfile && { opacity: 0.6 }]}
            activeOpacity={0.85}
          >
            {savingProfile ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.primaryBtnText}>SAVE PROFILE</Text>
            )}
          </TouchableOpacity>
        </View>

        {/* Club Config — admin only */}
        {user.role === 'admin' && (
          <>
            <Overline style={{ marginTop: spacing.lg, marginBottom: spacing.sm }}>
              Club Identity
            </Overline>
            <View style={styles.card}>
              <View style={styles.profileRow}>
                <TouchableOpacity
                  testID="pick-club-logo-btn"
                  onPress={pickClubLogo}
                  activeOpacity={0.85}
                  style={styles.clubLogoWrap}
                >
                  {clubLogo ? (
                    <Image source={{ uri: clubLogo }} style={styles.clubLogoImg} />
                  ) : (
                    <Text style={styles.logoLetter}>
                      {(clubName || 'C').slice(0, 1).toUpperCase()}
                    </Text>
                  )}
                  <View style={styles.editIcon}>
                    <Ionicons name="camera" size={14} color="#fff" />
                  </View>
                </TouchableOpacity>
                <View style={{ flex: 1, marginLeft: spacing.md }}>
                  <Muted>Customise your club</Muted>
                  <Title style={{ fontSize: 18, marginTop: 4 }}>{clubName || 'Club Dodo'}</Title>
                </View>
              </View>

              <Text style={[styles.label, { marginTop: spacing.md }]}>CLUB NAME</Text>
              <TextInput
                testID="club-name-input"
                value={clubName}
                onChangeText={setClubName}
                style={styles.input}
                placeholderTextColor={colors.textMuted}
              />

              <TouchableOpacity
                testID="save-club-btn"
                onPress={saveClub}
                disabled={savingClub}
                style={[styles.primaryBtn, savingClub && { opacity: 0.6 }]}
                activeOpacity={0.85}
              >
                {savingClub ? (
                  <ActivityIndicator color="#fff" />
                ) : (
                  <Text style={styles.primaryBtnText}>SAVE CLUB</Text>
                )}
              </TouchableOpacity>
            </View>

            <Overline style={{ marginTop: spacing.lg, marginBottom: spacing.sm }}>
              Match editors
            </Overline>
            <View style={[styles.card, { padding: 0, overflow: 'hidden' }]}>
              {allUsers
                .filter((u) => u.id !== user.id)
                .map((u) => (
                  <View key={u.id} style={styles.memberRow}>
                    <Avatar
                      uri={u.profile_picture}
                      size={36}
                      name={u.name}
                      shirt={u.shirt_number || undefined}
                    />
                    <View style={{ flex: 1, marginLeft: spacing.md }}>
                      <Text style={styles.memberName}>{u.name}</Text>
                      <Muted style={{ fontSize: 11 }}>{u.email}</Muted>
                    </View>
                    <TouchableOpacity
                      testID={`toggle-edit-${u.id}`}
                      onPress={() => toggleEdit(u.id, !u.can_edit_matches)}
                      style={[
                        styles.toggleBtn,
                        u.can_edit_matches && styles.toggleBtnOn,
                      ]}
                      activeOpacity={0.85}
                    >
                      <Text
                        style={[
                          styles.toggleText,
                          u.can_edit_matches && styles.toggleTextOn,
                        ]}
                      >
                        {u.can_edit_matches ? 'EDITOR' : 'GRANT'}
                      </Text>
                    </TouchableOpacity>
                  </View>
                ))}
              {allUsers.filter((u) => u.id !== user.id).length === 0 && (
                <Muted style={{ padding: spacing.lg }}>
                  No other users yet.
                </Muted>
              )}
            </View>

            <Overline style={{ marginTop: spacing.lg, marginBottom: spacing.sm }}>
              Danger zone
            </Overline>

            <TouchableOpacity
              testID="reset-matches-btn"
              onPress={resetMatches}
              style={[styles.dangerBtn, { borderColor: colors.warning, marginBottom: spacing.sm }]}
              activeOpacity={0.85}
            >
              <Ionicons name="calendar-clear-outline" size={18} color={colors.warning} />
              <View style={{ flex: 1 }}>
                <Text style={[styles.dangerTitle, { color: colors.warning }]}>
                  RESET MATCHES ONLY
                </Text>
                <Text style={styles.dangerSub}>
                  Wipes fixtures & history. Keeps players & career stats.
                </Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color={colors.warning} />
            </TouchableOpacity>

            <TouchableOpacity
              testID="reset-league-btn"
              onPress={resetLeague}
              style={[styles.dangerBtn, { borderColor: colors.warning, marginBottom: spacing.sm }]}
              activeOpacity={0.85}
            >
              <Ionicons name="trophy-outline" size={18} color={colors.warning} />
              <View style={{ flex: 1 }}>
                <Text style={[styles.dangerTitle, { color: colors.warning }]}>
                  NEW SEASON · RESET STANDINGS
                </Text>
                <Text style={styles.dangerSub}>
                  Zeros W/D/L/points for everyone. Goals & assists kept.
                </Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color={colors.warning} />
            </TouchableOpacity>

            <TouchableOpacity
              testID="reset-app-data-btn"
              onPress={resetAppData}
              style={styles.dangerBtn}
              activeOpacity={0.85}
            >
              <Ionicons name="trash-bin-outline" size={18} color={colors.danger} />
              <View style={{ flex: 1 }}>
                <Text style={styles.dangerTitle}>RESET EVERYTHING</Text>
                <Text style={styles.dangerSub}>
                  Deletes all matches & non-admin players. Zeros admin stats.
                </Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color={colors.danger} />
            </TouchableOpacity>
          </>
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
  headerRow: { flexDirection: 'row', alignItems: 'center', marginBottom: spacing.md },
  logoutBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: spacing.md,
    height: 38,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.md,
  },
  logoutText: {
    color: colors.textPrimary,
    fontWeight: '900',
    fontSize: 11,
    letterSpacing: 1,
  },
  card: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.lg,
    padding: spacing.lg,
  },
  profileRow: { flexDirection: 'row', alignItems: 'center', marginBottom: spacing.md },
  editIcon: {
    position: 'absolute',
    right: -2,
    top: -2,
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: colors.surface,
  },
  roleTag: {
    marginTop: 4,
    color: colors.primary,
    fontWeight: '900',
    letterSpacing: 1.5,
    fontSize: 11,
  },
  statLine: {
    marginTop: 4,
    color: colors.textSecondary,
    fontSize: 12,
    fontWeight: '700',
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
  primaryBtn: {
    marginTop: spacing.lg,
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
  clubLogoWrap: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: colors.surfaceAccent,
    borderWidth: 2,
    borderColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
  clubLogoImg: { width: '100%', height: '100%' },
  logoLetter: {
    color: colors.primary,
    fontSize: 32,
    fontWeight: '900',
  },
  memberRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  memberName: {
    color: colors.textPrimary,
    fontWeight: '800',
    fontSize: 14,
  },
  toggleBtn: {
    paddingHorizontal: spacing.md,
    height: 34,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.background,
  },
  toggleBtnOn: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  toggleText: {
    color: colors.textSecondary,
    fontWeight: '900',
    fontSize: 11,
    letterSpacing: 1.2,
  },
  toggleTextOn: { color: '#fff' },
  chipRow: { flexDirection: 'row', gap: 8, flexWrap: 'wrap' },
  posChip: {
    paddingHorizontal: spacing.md,
    height: 38,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.background,
    minWidth: 54,
  },
  posChipActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  posChipText: {
    color: colors.textSecondary,
    fontWeight: '900',
    letterSpacing: 1,
    fontSize: 13,
  },
  posChipTextActive: { color: '#fff' },
  posGroupLabel: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.8,
    marginBottom: 6,
    textTransform: 'uppercase',
  },
  dangerBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.danger,
    borderRadius: radii.md,
    padding: spacing.md,
  },
  dangerTitle: {
    color: colors.danger,
    fontWeight: '900',
    letterSpacing: 1.2,
    fontSize: 13,
  },
  dangerSub: {
    color: colors.textSecondary,
    fontSize: 11,
    fontWeight: '600',
    marginTop: 2,
  },
});
