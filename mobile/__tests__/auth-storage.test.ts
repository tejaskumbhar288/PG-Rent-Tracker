jest.mock('expo-secure-store', () => ({
  setItemAsync: jest.fn(),
  getItemAsync: jest.fn(),
  deleteItemAsync: jest.fn(),
}));

import * as SecureStore from 'expo-secure-store';

import { clearToken, getToken, saveToken } from '@/lib/auth-storage';

const setItemAsync = SecureStore.setItemAsync as jest.MockedFunction<
  typeof SecureStore.setItemAsync
>;
const getItemAsync = SecureStore.getItemAsync as jest.MockedFunction<
  typeof SecureStore.getItemAsync
>;
const deleteItemAsync = SecureStore.deleteItemAsync as jest.MockedFunction<
  typeof SecureStore.deleteItemAsync
>;

beforeEach(() => {
  jest.clearAllMocks();
});

describe('auth storage', () => {
  it('saves a token and reads it back', async () => {
    setItemAsync.mockResolvedValue(undefined);
    getItemAsync.mockResolvedValue('a-token');

    await expect(saveToken('a-token')).resolves.toBe(true);
    expect(setItemAsync).toHaveBeenCalledWith('pgrent.auth.token', 'a-token');
    await expect(getToken()).resolves.toBe('a-token');
  });

  it('reads back nothing once the token is cleared', async () => {
    deleteItemAsync.mockResolvedValue(undefined);
    getItemAsync.mockResolvedValue(null);

    await expect(clearToken()).resolves.toBe(true);
    expect(deleteItemAsync).toHaveBeenCalledWith('pgrent.auth.token');
    await expect(getToken()).resolves.toBeNull();
  });

  it('treats an undefined read as no token', async () => {
    // jest-expo's native-module mock resolves undefined rather than null.
    getItemAsync.mockResolvedValue(undefined as unknown as string | null);

    await expect(getToken()).resolves.toBeNull();
  });

  it('degrades instead of throwing when the keystore fails', async () => {
    const boom = new Error('keystore unavailable');
    getItemAsync.mockRejectedValue(boom);
    setItemAsync.mockRejectedValue(boom);
    deleteItemAsync.mockRejectedValue(boom);

    await expect(getToken()).resolves.toBeNull();
    await expect(saveToken('a-token')).resolves.toBe(false);
    await expect(clearToken()).resolves.toBe(false);
  });
});
