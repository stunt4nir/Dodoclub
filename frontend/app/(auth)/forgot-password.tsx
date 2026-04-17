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
} from 'react-native';
import { useRouter, Link } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { api } from '../../src/api';
import { colors, spacing, radii } from '../../src/theme';
import { Display, Overline, Muted } from '../../src/typography';

type ForgotResponse = {
  ok: boolean;
  dev_code: string | null;
  message: string;
};

export default function ForgotPasswordScreen() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [devCode, setDevCode] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  const onSubmit = async () => {
    setErr(null);
    if (!email.trim()) {
      setErr('Enter your email.');
      return;
    }
    setLoading(true);
    try {
      const res = await api<ForgotResponse>('/auth/forgot-password', {
        method: 'POST',
        body: { email: email.trim() },
        auth: false,
      });
      setDevCode(res.dev_code);
      setSubmitted(true);
    } catch (e: any) {
      setErr(e.message || 'Failed to send reset code');
    } finally {
      setLoading(false);
    }
  };

  const goReset = () => {
    router.push({
      pathname: '/(auth)/reset-password',
      params: { email: email.trim(), code: devCode || '' },
    });
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
            testID="forgot-back-btn"
            onPress={() => router.back()}
            style={styles.backBtn}
            hitSlop={12}
          >
            <Ionicons name="chevron-back" size={22} color={colors.textPrimary} />
          </TouchableOpacity>

          <View style={styles.brand}>
            <Display>Reset Password</Display>
            <Overline style={{ marginTop: 4 }}>
              Get a one-time code
            </Overline>
          </View>

          {!submitted ? (
            <View style={styles.form}>
              <Text style={styles.label}>EMAIL</Text>
              <TextInput
                testID="forgot-email-input"
                value={email}
                onChangeText={setEmail}
                autoCapitalize="none"
                keyboardType="email-address"
                placeholder="you@clubdodo.com"
                placeholderTextColor={colors.textMuted}
                style={styles.input}
              />

              {err && (
                <Text testID="forgot-error" style={styles.error}>
                  {err}
                </Text>
              )}

              <TouchableOpacity
                testID="forgot-submit-btn"
                activeOpacity={0.85}
                onPress={onSubmit}
                disabled={loading}
                style={[styles.primaryBtn, loading && { opacity: 0.6 }]}
              >
                {loading ? (
                  <ActivityIndicator color="#fff" />
                ) : (
                  <Text style={styles.primaryBtnText}>SEND CODE</Text>
                )}
              </TouchableOpacity>

              <View style={styles.switchRow}>
                <Muted>Remembered it?</Muted>
                <Link href="/(auth)/login" asChild>
                  <TouchableOpacity testID="forgot-go-login">
                    <Text style={styles.link}>  Back to sign in</Text>
                  </TouchableOpacity>
                </Link>
              </View>
            </View>
          ) : (
            <View style={styles.form}>
              {devCode ? (
                <>
                  <Overline>Your 6-digit code</Overline>
                  <View testID="dev-code-box" style={styles.codeBox}>
                    <Text style={styles.codeValue}>{devCode}</Text>
                  </View>
                  <Muted style={{ marginTop: spacing.sm }}>
                    This code expires in 60 minutes.
                  </Muted>
                </>
              ) : (
                <Muted>
                  If that email is registered, a code has been generated.
                </Muted>
              )}

              <TouchableOpacity
                testID="forgot-continue-btn"
                activeOpacity={0.85}
                onPress={goReset}
                style={styles.primaryBtn}
              >
                <Text style={styles.primaryBtnText}>CONTINUE</Text>
              </TouchableOpacity>
            </View>
          )}
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
  codeBox: {
    marginTop: spacing.sm,
    backgroundColor: colors.background,
    borderWidth: 2,
    borderColor: colors.primary,
    borderRadius: radii.md,
    paddingVertical: spacing.lg,
    alignItems: 'center',
  },
  codeValue: {
    color: colors.primary,
    fontSize: 42,
    fontWeight: '900',
    letterSpacing: 8,
  },
});
