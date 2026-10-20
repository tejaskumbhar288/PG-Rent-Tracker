import { zodResolver } from '@hookform/resolvers/zod';
import { Link } from 'expo-router';
import { Controller, useForm } from 'react-hook-form';
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { useSignup } from '@/api/use-auth';
import { FormField } from '@/components/form-field';
import { PrimaryButton } from '@/components/primary-button';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { describeApiError } from '@/lib/api-errors';
import { type SignupValues, signupSchema } from '@/lib/auth-schemas';

export default function SignupScreen() {
  const theme = useTheme();
  const signup = useSignup();
  const { control, handleSubmit, formState } = useForm<SignupValues>({
    resolver: zodResolver(signupSchema),
    defaultValues: { name: '', phone: '', email: '', password: '' },
  });

  const submit = handleSubmit((values) => {
    signup.mutate({
      name: values.name.trim(),
      phone: values.phone,
      password: values.password,
      // Email is optional: send nothing rather than an empty string.
      ...(values.email === '' ? {} : { email: values.email }),
    });
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
            <ThemedText type="subtitle">Create account</ThemedText>
            <ThemedText themeColor="textSecondary">
              This account holds your PG&apos;s tenants and rent records.
            </ThemedText>

            <Controller
              control={control}
              name="name"
              render={({ field: { onChange, onBlur, value } }) => (
                <FormField
                  label="YOUR NAME"
                  autoCapitalize="words"
                  autoComplete="name"
                  placeholder="Suresh Kumar"
                  returnKeyType="next"
                  value={value}
                  onBlur={onBlur}
                  onChangeText={onChange}
                  error={formState.errors.name?.message}
                />
              )}
            />

            <Controller
              control={control}
              name="phone"
              render={({ field: { onChange, onBlur, value } }) => (
                <FormField
                  label="PHONE"
                  autoComplete="tel"
                  keyboardType="phone-pad"
                  placeholder="98765 43210"
                  returnKeyType="next"
                  value={value}
                  onBlur={onBlur}
                  onChangeText={onChange}
                  error={formState.errors.phone?.message}
                />
              )}
            />

            <Controller
              control={control}
              name="email"
              render={({ field: { onChange, onBlur, value } }) => (
                <FormField
                  label="EMAIL (OPTIONAL)"
                  autoCapitalize="none"
                  autoCorrect={false}
                  autoComplete="email"
                  keyboardType="email-address"
                  placeholder="you@example.com"
                  returnKeyType="next"
                  value={value}
                  onBlur={onBlur}
                  onChangeText={onChange}
                  error={formState.errors.email?.message}
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
                  autoComplete="new-password"
                  secureTextEntry
                  placeholder="At least 8 characters"
                  returnKeyType="go"
                  value={value}
                  onBlur={onBlur}
                  onChangeText={onChange}
                  onSubmitEditing={() => void submit()}
                  error={formState.errors.password?.message}
                />
              )}
            />

            {signup.isError ? (
              <ThemedText type="small" style={{ color: theme.statusError }}>
                {describeApiError(signup.error)}
              </ThemedText>
            ) : null}

            <PrimaryButton
              label="Create account"
              pendingLabel="Creating account…"
              pending={signup.isPending}
              onPress={submit}
            />

            <ThemedText type="small" themeColor="textSecondary" style={styles.footer}>
              Already have an account?{' '}
              <Link href="/login" style={{ color: theme.text }}>
                Log in
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
