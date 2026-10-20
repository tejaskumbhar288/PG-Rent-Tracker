/**
 * App configuration, sourced only from environment variables.
 *
 * `EXPO_PUBLIC_API_URL` is inlined into the bundle at build time by Expo.
 * On a real phone it must be the laptop's LAN IP (see mobile/.env.example),
 * never `localhost` — that would point at the device itself.
 */

/** Base URL of the backend API, e.g. `http://192.168.1.5:8000`. */
export const API_URL: string = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000';

/** All backend routes live under this prefix (CLAUDE.md §8). */
export const API_PREFIX = '/api/v1';
