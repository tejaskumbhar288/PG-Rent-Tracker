import { zodResolver } from '@hookform/resolvers/zod';
import { Link } from 'expo-router';
import { Controller, useForm } from 'react-hook-form';
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useLogin } from '@/api/use-auth';
import { FormField } from '@/components/form-field';
import { PrimaryButton } from '@/components/primary-button';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { describeApiError } from '@/lib/api-errors';
import { type LoginValues, loginSchema } from '@/lib/auth-schemas';

export default function LoginScreen() {
  const theme = useTheme();
  const login = useLogin();
  const { control, handleSubmit, formState } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { identifier: '', password: '' },
  });

  // On success the auth provider stores the token, which flips the root guard
  // and moves the owner to the dashboard — no navigation call needed here.
  const submit = handleSubmit((values) => {
    login.mutate({ identifier: values.identifier.trim(), password: values.password });
  });

  return (
    <ThemedView style={styles.container}>
      <SafeAreaView style={styles.safeArea}>
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
          style={styles.container}>
          <ScrollView
            contentContainerStyle={styles.content}
            keyboardShouldPersistTaps="handled">
            <ThemedText type="subtitle">Log in</ThemedText>
            <ThemedText themeColor="textSecondary">
              Use the phone number or email you signed up with.
            </ThemedText>

            <Controller
              control={control}
              name="identifier"
              render={({ field: { onChange, onBlur, value } }) => (
                <FormField
                  label="PHONE OR EMAIL"
                  autoCapitalize="none"
                  autoCorrect={false}
                  autoComplete="username"
                  keyboardType="default"
                  placeholder="98765 43210"
                  returnKeyType="next"
                  value={value}
                  onBlur={onBlur}
                  onChangeText={onChange}
                  error={formState.errors.identifier?.message}
                />
              )}
            />

            <Controller
              control={control}
              name="password"
              render={({ field: { onChange, onBlur, value } }) => (
                <FormField
                  label="PASSWORD"
                  autoCapitalize="none"
                  autoComplete="current-password"
                  secureTextEntry
                  returnKeyType="go"
                  value={value}
                  onBlur={onBlur}
                  onChangeText={onChange}
                  onSubmitEditing={() => void submit()}
                  error={formState.errors.password?.message}
                />
              )}
            />

            {login.isError ? (
              <ThemedText type="small" style={{ color: theme.statusError }}>
                {describeApiError(login.error)}
              </ThemedText>
            ) : null}

            <PrimaryButton
              label="Log in"
              pendingLabel="Logging in…"
              pending={login.isPending}
              onPress={submit}
            />

            <ThemedText type="small" themeColor="textSecondary" style={styles.footer}>
              Don&apos;t have an account?{' '}
              <Link href="/signup" style={{ color: theme.text }}>
                Sign up
              </Link>
            </ThemedText>
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  safeArea: {
    flex: 1,
  },
  content: {
    gap: Spacing.three,
    paddingHorizontal: Spacing.four,
    paddingTop: Spacing.six,
    paddingBottom: Spacing.four,
  },
  footer: {
    textAlign: 'center',
    paddingTop: Spacing.two,
  },
});
