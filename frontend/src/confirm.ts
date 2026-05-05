import { Alert, Platform } from 'react-native';

/**
 * Cross-platform confirm dialog that actually works on web.
 *
 * React Native's `Alert.alert` on react-native-web routes 3-button alerts
 * through `window.confirm` but the destructive button callback gets swallowed
 * silently in some Chromium builds. Using `window.confirm` directly on web
 * guarantees the user's choice is honoured.
 *
 * Returns a Promise<boolean> — true if confirmed, false if cancelled.
 */
export function confirm(
  title: string,
  message?: string,
  { confirmLabel = 'Delete', cancelLabel = 'Cancel', destructive = true } = {},
): Promise<boolean> {
  if (Platform.OS === 'web') {
    const text = message ? `${title}\n\n${message}` : title;
    // eslint-disable-next-line no-alert
    return Promise.resolve(window.confirm(text));
  }
  return new Promise<boolean>((resolve) => {
    Alert.alert(title, message, [
      { text: cancelLabel, style: 'cancel', onPress: () => resolve(false) },
      {
        text: confirmLabel,
        style: destructive ? 'destructive' : 'default',
        onPress: () => resolve(true),
      },
    ]);
  });
}
