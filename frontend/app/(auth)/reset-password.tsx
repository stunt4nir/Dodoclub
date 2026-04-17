import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { useRouter, useLocalSearchParams, Link } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { api } from '../../src/api';
import { useAuth } from '../../src/auth';
import { colors, spacing, radii } from '../../src/theme';
import { Display, Overline, Muted } from '../../src/typography';

export default function ResetPasswordScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ email?: string; code?: string }>();
  const { login } = useAuth();
  const [email, setEmail] = useState(params.email || '');
  const [code, setCode] = useState(params.code || '');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const onSubmit = async () => {
    setErr(null);
    if (!email.trim() || code.length !== 6 || password.length < 6) {
      setErr('Enter your email, 6-digit code, and a new password (min 6 chars).');
      return;
    }
    setLoading(true);
    try {
      await api('/auth/reset-password', {
        method: 'POST',
        body: {
          email: email.trim(),
          code: code.trim(),
          new_password: password,
        },
        auth: false,
      });
      // auto sign in with the new password
      try {
        await login(email.trim(), password);
        router.replace('/(tabs)');
      } catch {
        Alert.alert(
          'Password reset',
          'Your password has been reset. Please sign in.',
          [{ text: 'OK', onPress: () => router.replace('/(auth)/login') }]
        );
      }
    } catch (e: any) {
      setErr(e.message || 'Reset failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe} edges={['top', 'bottom']}>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={{ flex: 1 }}
      >
        <ScrollView
          contentContainerStyle={styles.scroll}
          keyboardShouldPersistTaps="handled"
        >
          <TouchableOpacity
            testID="reset-back-btn"
            onPress={() => router.back()}
            style={styles.backBtn}
            hitSlop={12}
          >
            <Ionicons name="chevron-back" size={22} color={colors.textPrimary} />
          </TouchableOpacity>

          <View style={styles.brand}>
            <Display>New Password</Display>
            <Overline style={{ marginTop: 4 }}>
              Enter your code to reset
            </Overline>
          </View>

          <View style={styles.form}>
            <Text style={styles.label}>EMAIL</Text>
            <TextInput
              testID="reset-email-input"
              value={email}
              onChangeText={setEmail}
              autoCapitalize="none"
              keyboardType="email-address"
              placeholder="you@clubdodo.com"
              placeholderTextColor={colors.textMuted}
              style={styles.input}
            />

            <Text style={[styles.label, { marginTop: spacing.md }]}>6-DIGIT CODE</Text>
            <TextInput
              testID="reset-code-input"
              value={code}
              onChangeText={(t) => setCode(t.replace(/[^0-9]/g, '').slice(0, 6))}
              keyboardType="number-pad"
              placeholder="123456"
              placeholderTextColor={colors.textMuted}
              style={[styles.input, styles.codeInput]}
              maxLength={6}
            />

            <Text style={[styles.label, { marginTop: spacing.md }]}>NEW PASSWORD</Text>
            <TextInput
              testID="reset-password-input"
              value={password}
              onChangeText={setPassword}
              secureTextEntry
              placeholder="At least 6 characters"
              placeholderTextColor={colors.textMuted}
              style={styles.input}
            />

            {err && (
              <Text testID="reset-error" style={styles.error}>
                {err}
              </Text>
            )}

            <TouchableOpacity
              testID="reset-submit-btn"
              activeOpacity={0.85}
              onPress={onSubmit}
              disabled={loading}
              style={[styles.primaryBtn, loading && { opacity: 0.6 }]}
            >
              {loading ? (
                <ActivityIndicator color="#fff" />
              ) : (
                <Text style={styles.primaryBtnText}>RESET & SIGN IN</Text>
              )}
            </TouchableOpacity>

            <View style={styles.switchRow}>
              <Muted>Need a new code?</Muted>
              <Link href="/(auth)/forgot-password" asChild>
                <TouchableOpacity testID="reset-go-forgot">
                  <Text style={styles.link}>  Request again</Text>
                </TouchableOpacity>
              </Link>
            </View>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  scroll: {
    flexGrow: 1,
    justifyContent: 'center',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.xl,
  },
  backBtn: {
    width: 40,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radii.md,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing.lg,
  },
  brand: { alignItems: 'center', marginBottom: spacing.xl },
  form: {
    backgroundColor: colors.surface,
    borderRadius: radii.lg,
    padding: spacing.lg,
    borderWidth: 1,
    borderColor: colors.border,
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
  codeInput: {
    fontSize: 26,
    fontWeight: '900',
    letterSpacing: 8,
    textAlign: 'center',
    height: 58,
  },
  error: { color: colors.danger, marginTop: spacing.md, fontSize: 13 },
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
    fontSize: 18,
    fontWeight: '900',
    letterSpacing: 1,
  },
  switchRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    marginTop: spacing.lg,
    alignItems: 'center',
  },
  link: { color: colors.primary, fontWeight: '800', fontSize: 13 },
});
