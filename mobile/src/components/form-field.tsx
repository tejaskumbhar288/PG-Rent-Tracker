import { useState } from 'react';
import {
  Pressable,
  StyleSheet,
  type StyleProp,
  TextInput,
  type TextInputProps,
  type TextStyle,
  View,
} from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

type Props = Omit<TextInputProps, 'style'> & {
  label: string;
  /** Validation or server message shown under the input. */
  error?: string;
  /** Extra styles for the input itself, e.g. a taller box for a multiline field. */
  inputStyle?: StyleProp<TextStyle>;
};

/** Labelled text input with an inline error, sized for a thumb on a phone. */
export function FormField({ label, error, secureTextEntry, inputStyle, ...inputProps }: Props) {
  const theme = useTheme();
  const [revealed, setRevealed] = useState(false);
  const isPassword = secureTextEntry === true;

  return (
    <View style={styles.container}>
      <View style={styles.labelRow}>
        <ThemedText type="smallBold" themeColor="textSecondary">
          {label}
        </ThemedText>
        {isPassword ? (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={revealed ? 'Hide password' : 'Show password'}
            hitSlop={Spacing.two}
            onPress={() => setRevealed((previous) => !previous)}>
            <ThemedText type="smallBold" themeColor="textSecondary">
              {revealed ? 'Hide' : 'Show'}
            </ThemedText>
          </Pressable>
        ) : null}
      </View>

      <TextInput
        accessibilityLabel={label}
        placeholderTextColor={theme.textSecondary}
        secureTextEntry={isPassword && !revealed}
        style={[
          styles.input,
          {
            backgroundColor: theme.backgroundElement,
            color: theme.text,
            borderColor: error === undefined ? 'transparent' : theme.statusError,
          },
          inputStyle,
        ]}
        {...inputProps}
      />

      {error === undefined ? null : (
        <ThemedText type="small" style={{ color: theme.statusError }}>
          {error}
        </ThemedText>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: Spacing.one,
  },
  labelRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  input: {
    minHeight: 48,
    borderRadius: Spacing.three,
    borderWidth: 1,
    paddingHorizontal: Spacing.three,
    fontSize: 16,
  },
});
