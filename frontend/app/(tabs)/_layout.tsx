import React from 'react';
import { Tabs, Redirect } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { View, ActivityIndicator, Platform } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useAuth } from '../../src/auth';
import { colors } from '../../src/theme';

export default function TabsLayout() {
  const { user, loading } = useAuth();
  const insets = useSafeAreaInsets();

  if (loading) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.background, alignItems: 'center', justifyContent: 'center' }}>
        <ActivityIndicator color={colors.primary} />
      </View>
    );
  }
  if (!user) return <Redirect href="/(auth)/login" />;

  // Lift the tab-bar icons ~2 cm (≈75 dp) above the system nav / gesture pill
  // to avoid the Samsung S25 Ultra overlap. We add a large bottom padding so
  // the icons sit visually higher while the bar itself remains glued to the
  // bottom.
  const bottomInset = insets.bottom;
  const LIFT_DP = 150; // ≈ 4 cm — two cumulative lifts of 2 cm
  const ANDROID_FLOOR = 0;
  const nativeExtra = Platform.OS === 'android' ? Math.max(ANDROID_FLOOR, bottomInset) : bottomInset;
  const extraBottom = nativeExtra + LIFT_DP;
  const tabBarHeight = 50 + extraBottom;
  const tabBarPaddingBottom = extraBottom;

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarStyle: {
          backgroundColor: colors.surface,
          borderTopColor: colors.border,
          borderTopWidth: 1,
          height: tabBarHeight,
          paddingBottom: tabBarPaddingBottom,
          paddingTop: 2,
        },
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.textMuted,
        tabBarLabelStyle: {
          fontSize: 11,
          fontWeight: '800',
          letterSpacing: 1,
          textTransform: 'uppercase',
          marginTop: 0,
        },
        tabBarIconStyle: {
          marginBottom: 0,
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Home',
          tabBarIcon: ({ color }) => (
            <Ionicons name="football-outline" size={24} color={color} />
          ),
          tabBarButtonTestID: 'nav-home-tab',
        }}
      />
      <Tabs.Screen
        name="squad"
        options={{
          title: 'Squad',
          tabBarIcon: ({ color }) => (
            <Ionicons name="people-outline" size={24} color={color} />
          ),
          tabBarButtonTestID: 'nav-squad-tab',
        }}
      />
      <Tabs.Screen
        name="matches"
        options={{
          title: 'Matches',
          tabBarIcon: ({ color }) => (
            <Ionicons name="calendar-outline" size={24} color={color} />
          ),
          tabBarButtonTestID: 'nav-matches-tab',
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: 'Profile',
          tabBarIcon: ({ color }) => (
            <Ionicons name="person-circle-outline" size={24} color={color} />
          ),
          tabBarButtonTestID: 'nav-profile-tab',
        }}
      />
    </Tabs>
  );
}
