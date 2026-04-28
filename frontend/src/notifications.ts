import { Platform } from 'react-native';
import * as Notifications from 'expo-notifications';

let configured = false;

async function configure() {
  if (configured) return;
  configured = true;
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowAlert: true,
      shouldShowBanner: true,
      shouldShowList: true,
      shouldPlaySound: false,
      shouldSetBadge: false,
    }),
  });
  if (Platform.OS === 'android') {
    try {
      await Notifications.setNotificationChannelAsync('default', {
        name: 'Match reminders',
        importance: Notifications.AndroidImportance.DEFAULT,
        vibrationPattern: [0, 250, 250, 250],
        lightColor: '#FF6A00',
      });
    } catch {
      /* ignore */
    }
  }
}

let permissionAsked = false;
export async function ensurePermission(): Promise<boolean> {
  await configure();
  try {
    const settings = await Notifications.getPermissionsAsync();
    if (settings.granted) return true;
    if (permissionAsked) return false;
    permissionAsked = true;
    const req = await Notifications.requestPermissionsAsync();
    return !!req.granted;
  } catch {
    return false;
  }
}

/** Schedule a one-shot local notification at a given Date.
 *  Returns the notification id, or null if not scheduled. */
export async function scheduleAt(
  date: Date,
  title: string,
  body: string,
  identifier?: string,
): Promise<string | null> {
  if (date.getTime() <= Date.now() + 15_000) return null; // already past / too soon
  const ok = await ensurePermission();
  if (!ok) return null;
  try {
    const id = await Notifications.scheduleNotificationAsync({
      content: { title, body, data: { kind: 'match-reminder' } },
      trigger: { type: Notifications.SchedulableTriggerInputTypes.DATE, date },
      identifier,
    });
    return id;
  } catch {
    return null;
  }
}

export async function cancelByIdentifier(id: string) {
  try {
    await Notifications.cancelScheduledNotificationAsync(id);
  } catch {
    /* ignore */
  }
}

export async function listScheduled(): Promise<string[]> {
  try {
    const items = await Notifications.getAllScheduledNotificationsAsync();
    return items.map((i) => i.identifier);
  } catch {
    return [];
  }
}

/** Schedule a "Match in 2 hours" reminder for a confirmed match. Idempotent
 *  — uses a deterministic identifier per (match, kind). */
export async function scheduleMatchReminders(opts: {
  matchId: string;
  matchDateIso: string;
  iVoted: 'yes' | 'no' | 'reserve' | null;
  matchStatus: string;
}) {
  const { matchId, matchDateIso, iVoted, matchStatus } = opts;
  const matchDate = new Date(matchDateIso);
  if (Number.isNaN(matchDate.getTime())) return;

  // 1. "Match in 2h" — only if user voted YES
  if (iVoted === 'yes') {
    const remind = new Date(matchDate.getTime() - 2 * 60 * 60 * 1000);
    await scheduleAt(
      remind,
      '⚽ Match in 2 hours',
      `Don't forget — kickoff at ${matchDate.toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
      })}.`,
      `match-${matchId}-2h`,
    );
  }

  // 2. "Don't forget to vote" — 24h before kickoff if voting still open
  if (matchStatus === 'voting' && iVoted == null) {
    const voteRemind = new Date(matchDate.getTime() - 24 * 60 * 60 * 1000);
    await scheduleAt(
      voteRemind,
      '🗳 Vote now',
      'Match kicks off tomorrow — let your team know if you can play.',
      `match-${matchId}-vote`,
    );
  }
}
