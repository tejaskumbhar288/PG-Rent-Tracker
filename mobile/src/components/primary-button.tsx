import { Pressable, StyleSheet } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

type Props = {
  label: string;
  /** Shown instead of `label` while `pending` is true. */
  pendingLabel?: string;
  onPress: () => void;
  disabled?: boolean;
  pending?: boolean;
};

/** Full-width primary action, at least 48dp tall (CLAUDE.md §2). */
export function PrimaryButton({ label, pendingLabel, onPress, disabled, pending }: Props) {
  const theme = useTheme();
  const isBusy = pending === true;
  const isDisabled = disabled === true || isBusy;

  return (
    <Pressable
      accessibilityRole="button"
      // A stable name, so assistive tech announces the action rather than its
      // transient "…ing" wording.
      accessibilityLabel={label}
      accessibilityState={{ disabled: isDisabled, busy: isBusy }}
      disabled={isDisabled}
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        { backgroundColor: theme.text, opacity: isDisabled ? 0.5 : pressed ? 0.8 : 1 },
      ]}>
      <ThemedText type="smallBold" style={{ color: theme.background }}>
        {isBusy ? (pendingLabel ?? label) : label}
      </ThemedText>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    minHeight: 48,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: Spacing.three,
    paddingHorizontal: Spacing.four,
  },
});
