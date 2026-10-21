import { zodResolver } from '@hookform/resolvers/zod';
import type { ReactNode } from 'react';
import { useEffect, useState } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { Pressable, StyleSheet } from 'react-native';

import { ApiError } from '@/api/client';
import { usePg, useUpdatePg } from '@/api/use-pg';
import { FormField } from '@/components/form-field';
import { PrimaryButton } from '@/components/primary-button';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { describeApiError } from '@/lib/api-errors';
import { dueDayLabel } from '@/lib/pg-format';
import { type PgValues, pgSchema } from '@/lib/pg-schemas';
import type { Pg } from '@/types/pg';

function toFormValues(pg: Pg): PgValues {
  return { name: pg.name, address: pg.address ?? '', dueDay: String(pg.default_rent_due_day) };
}

/**
 * The PG's name, address and rent due day, editable in place.
 *
 * Settings stays a layout file (CLAUDE.md §9), so everything about the PG —
 * fetching, validating, saving and the four states it can be in — lives here.
 */
export function PgDetailsCard() {
  const theme = useTheme();
  const query = usePg();
  const update = useUpdatePg();
  const [isEditing, setIsEditing] = useState(false);

  const { control, handleSubmit, reset, formState } = useForm<PgValues>({
    resolver: zodResolver(pgSchema),
    defaultValues: { name: '', address: '', dueDay: '' },
  });

  const pg = query.data;

  // Follow the server's copy, so Edit never opens on a stale value — or on an
  // empty form, which is what the defaults above would otherwise show.
  useEffect(() => {
    if (pg !== undefined) {
      reset(toFormValues(pg));
    }
  }, [pg, reset]);

  const submit = handleSubmit((values) => {
    const address = values.address.trim();
    update.mutate(
      {
        name: values.name.trim(),
        // An empty field means "no address"; null is what clears it server-side.
        address: address === '' ? null : address,
        default_rent_due_day: Number(values.dueDay),
      },
      { onSuccess: () => setIsEditing(false) },
    );
  });

  const cancelEditing = () => {
    if (pg !== undefined) {
      reset(toFormValues(pg));
    }
    update.reset();
    setIsEditing(false);
  };

  // Checked before describeApiError, which would render the API's lowercase
  // "pg not found" as "Pg not found" — accurate and useless to the owner.
  const hasNoPg = query.error instanceof ApiError && query.error.status === 404;

  let body: ReactNode;
  if (query.isLoading) {
    body = (
      <ThemedText type="small" themeColor="textSecondary">
        Loading…
      </ThemedText>
    );
  } else if (hasNoPg) {
    body = (
      <>
        <ThemedText>No PG set up yet.</ThemedText>
        <ThemedText type="small" themeColor="textSecondary">
          Please contact support.
        </ThemedText>
      </>
    );
  } else if (query.isError) {
    body = (
      <ThemedText type="small" style={{ color: theme.statusError }}>
        {describeApiError(query.error)}
      </ThemedText>
    );
  } else if (pg === undefined) {
    body = null;
  } else if (!isEditing) {
    body = (
      <>
        <ThemedText>{pg.name}</ThemedText>
        <ThemedText type="small" themeColor="textSecondary">
          {pg.address ?? 'No address yet'}
        </ThemedText>
        <ThemedText type="small" themeColor="textSecondary">
          {dueDayLabel(pg.default_rent_due_day)}
        </ThemedText>

        <Pressable
          accessibilityRole="button"
          onPress={() => setIsEditing(true)}
          style={({ pressed }) => [
            styles.action,
            { backgroundColor: theme.backgroundSelected, opacity: pressed ? 0.7 : 1 },
          ]}>
          <ThemedText type="smallBold">Edit</ThemedText>
        </Pressable>
      </>
    );
  } else {
    body = (
      <>
        <Controller
          control={control}
          name="name"
          render={({ field: { onChange, onBlur, value } }) => (
            <FormField
              label="PG NAME"
              autoCapitalize="words"
              placeholder="Sri Sai PG"
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
          name="address"
          render={({ field: { onChange, onBlur, value } }) => (
            <FormField
              label="ADDRESS (OPTIONAL)"
              autoCapitalize="words"
              multiline
              inputStyle={styles.addressInput}
              placeholder="12, 4th Cross, Koramangala"
              value={value}
              onBlur={onBlur}
              onChangeText={onChange}
              error={formState.errors.address?.message}
            />
          )}
        />

        <Controller
          control={control}
          name="dueDay"
          render={({ field: { onChange, onBlur, value } }) => (
            <FormField
              label="RENT DUE DAY"
              keyboardType="number-pad"
              maxLength={2}
              placeholder="5"
              returnKeyType="done"
              value={value}
              onBlur={onBlur}
              onChangeText={onChange}
              error={formState.errors.dueDay?.message}
            />
          )}
        />
        <ThemedText type="small" themeColor="textSecondary">
          1–28, so it works in February too.
        </ThemedText>

        {update.isError ? (
          <ThemedText type="small" style={{ color: theme.statusError }}>
            {describeApiError(update.error)}
          </ThemedText>
        ) : null}

        <PrimaryButton
          label="Save changes"
          pendingLabel="Saving…"
          pending={update.isPending}
          onPress={submit}
        />

        <Pressable
          accessibilityRole="button"
          disabled={update.isPending}
          onPress={cancelEditing}
          style={({ pressed }) => [styles.cancel, { opacity: pressed ? 0.7 : 1 }]}>
          <ThemedText type="smallBold" themeColor="textSecondary">
            Cancel
          </ThemedText>
        </Pressable>
      </>
    );
  }

  return (
    <ThemedView type="backgroundElement" style={styles.card}>
      <ThemedText type="smallBold" themeColor="textSecondary">
        PG DETAILS
      </ThemedText>
      {body}
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  card: {
    gap: Spacing.three,
    padding: Spacing.four,
    borderRadius: Spacing.three,
  },
  action: {
    alignSelf: 'flex-start',
    paddingHorizontal: Spacing.four,
    paddingVertical: Spacing.two,
    borderRadius: Spacing.five,
  },
  cancel: {
    alignSelf: 'center',
    paddingVertical: Spacing.two,
  },
  addressInput: {
    minHeight: 72,
    paddingTop: Spacing.two,
    textAlignVertical: 'top',
  },
});
