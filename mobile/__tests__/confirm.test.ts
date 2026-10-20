import { Alert } from 'react-native';

import { confirmAction } from '@/lib/confirm';

/**
 * These run on the native path (jest-expo reports Platform.OS as 'ios'). The web
 * branch swaps in the browser dialog, because react-native-web's Alert is a
 * no-op — that half is checked by hand in a browser.
 */
describe('confirmAction', () => {
  it('offers a cancel and a destructive action', () => {
    const spy = jest.spyOn(Alert, 'alert').mockImplementation(() => undefined);
    const onConfirm = jest.fn();

    confirmAction({
      title: 'Log out?',
      message: 'You will need your password to log back in.',
      confirmLabel: 'Log out',
      onConfirm,
    });

    expect(spy).toHaveBeenCalledTimes(1);
    const [title, message, buttons] = spy.mock.calls[0];
    expect(title).toBe('Log out?');
    expect(message).toContain('password');
    expect(buttons?.map((button) => button.text)).toEqual(['Cancel', 'Log out']);
    expect(buttons?.[1].style).toBe('destructive');
    expect(onConfirm).not.toHaveBeenCalled();

    spy.mockRestore();
  });

  it('runs the action only when the destructive button is pressed', () => {
    const spy = jest.spyOn(Alert, 'alert').mockImplementation(() => undefined);
    const onConfirm = jest.fn();

    confirmAction({ title: 'Log out?', message: 'Sure?', confirmLabel: 'Log out', onConfirm });
    const buttons = spy.mock.calls[0][2];

    buttons?.[0].onPress?.();
    expect(onConfirm).not.toHaveBeenCalled();

    buttons?.[1].onPress?.();
    expect(onConfirm).toHaveBeenCalledTimes(1);

    spy.mockRestore();
  });
});
