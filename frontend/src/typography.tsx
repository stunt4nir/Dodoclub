import React from 'react';
import { Text, TextProps, StyleSheet } from 'react-native';
import { colors } from './theme';

// Big display text inspired by Bebas Neue — uses system condensed weight fallback
export function Display({ style, ...rest }: TextProps) {
  return <Text {...rest} style={[styles.display, style]} />;
}

export function Title({ style, ...rest }: TextProps) {
  return <Text {...rest} style={[styles.title, style]} />;
}

export function Overline({ style, ...rest }: TextProps) {
  return <Text {...rest} style={[styles.overline, style]} />;
}

export function Body({ style, ...rest }: TextProps) {
  return <Text {...rest} style={[styles.body, style]} />;
}

export function Muted({ style, ...rest }: TextProps) {
  return <Text {...rest} style={[styles.muted, style]} />;
}

const styles = StyleSheet.create({
  display: {
    fontSize: 44,
    fontWeight: '900',
    color: colors.textPrimary,
    letterSpacing: -1,
    textTransform: 'uppercase',
    lineHeight: 44,
  },
  title: {
    fontSize: 22,
    fontWeight: '800',
    color: colors.textPrimary,
    letterSpacing: 0.2,
    textTransform: 'uppercase',
  },
  overline: {
    fontSize: 11,
    fontWeight: '800',
    color: colors.textSecondary,
    letterSpacing: 2,
    textTransform: 'uppercase',
  },
  body: {
    fontSize: 15,
    color: colors.textPrimary,
  },
  muted: {
    fontSize: 13,
    color: colors.textSecondary,
  },
});
