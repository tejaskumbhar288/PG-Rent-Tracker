import { Alert, Platform } from 'react-native';

type ConfirmOptions = {
  title: string;
  message: string;
  /** Label for the destructive action, e.g. "Log out". */
  confirmLabel: string;
  onConfirm: () => void;
};

/**
 * Ask the owner to confirm a destructive action.
 *
 * `Alert.alert` is an empty no-op in react-native-web (`class Alert { static
 * alert() {} }`), so on web the action would silently never happen. The browser's
 * own dialog stands in there, the same way `auth-storage` falls back to
 * `localStorage`.
 */
export function confirmAction({ title, message, confirmLabel, onConfirm }: ConfirmOptions): void {
  if (Platform.OS === 'web') {
    if (globalThis.confirm?.(`${title}\n\n${message}`) === true) {
      onConfirm();
    }
    return;
  }

  Alert.alert(title, message, [
    { text: 'Cancel', style: 'cancel' },
    { text: confirmLabel, style: 'destructive', onPress: onConfirm },
  ]);
}
