import React from 'react';
import { View, Text, Image, StyleSheet } from 'react-native';
import { colors, radii } from './theme';

type Props = {
  uri?: string | null;
  size?: number;
  shirt?: number | null;
  name?: string;
};

export default function Avatar({ uri, size = 48, shirt, name }: Props) {
  const initials = (name || '?')
    .split(' ')
    .map((p) => p[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();
  const inner = size - 4;
  return (
    <View style={{ width: size, height: size }}>
      <View
        style={[
          styles.ring,
          { width: size, height: size, borderRadius: size / 2 },
        ]}
      >
        {uri ? (
          <Image
            source={{ uri }}
            style={{ width: inner, height: inner, borderRadius: inner / 2 }}
          />
        ) : (
          <View
            style={[
              styles.fallback,
              { width: inner, height: inner, borderRadius: inner / 2 },
            ]}
          >
            <Text style={[styles.initials, { fontSize: size * 0.35 }]}>{initials}</Text>
          </View>
        )}
      </View>
      {shirt != null && (
        <View style={styles.shirtBadge}>
          <Text style={styles.shirtText}>{shirt}</Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  ring: {
    borderWidth: 2,
    borderColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.surface,
  },
  fallback: {
    backgroundColor: colors.surfaceAccent,
    alignItems: 'center',
    justifyContent: 'center',
  },
  initials: {
    color: colors.textPrimary,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  shirtBadge: {
    position: 'absolute',
    right: -4,
    bottom: -4,
    minWidth: 22,
    height: 22,
    paddingHorizontal: 4,
    borderRadius: radii.full,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 2,
    borderColor: colors.background,
  },
  shirtText: {
    color: '#fff',
    fontSize: 11,
    fontWeight: '900',
  },
});
