import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

const TOKEN_KEY = 'pgrent.auth.token';

/**
 * The owner's access token, held in the device keystore so they stay logged in
 * across app restarts.
 *
 * SecureStore has no web implementation and can throw on a device with a broken
 * keystore, so every call here degrades instead of throwing: a failed read
 * becomes "no token" (which lands the owner on the login screen) and a failed
 * write returns `false` — they are still logged in for this session, just not
 * after a restart.
 */
export async function saveToken(token: string): Promise<boolean> {
  try {
    if (Platform.OS === 'web') {
      globalThis.localStorage?.setItem(TOKEN_KEY, token);
    } else {
      await SecureStore.setItemAsync(TOKEN_KEY, token);
    }
    return true;
  } catch {
    return false;
  }
}

export async function getToken(): Promise<string | null> {
  try {
    if (Platform.OS === 'web') {
      return globalThis.localStorage?.getItem(TOKEN_KEY) ?? null;
    }
    // Returns undefined under jest-expo's native-module mock, hence the ??.
    return (await SecureStore.getItemAsync(TOKEN_KEY)) ?? null;
  } catch {
    return null;
  }
}

export async function clearToken(): Promise<boolean> {
  try {
    if (Platform.OS === 'web') {
      globalThis.localStorage?.removeItem(TOKEN_KEY);
    } else {
      await SecureStore.deleteItemAsync(TOKEN_KEY);
    }
    return true;
  } catch {
    return false;
  }
}
