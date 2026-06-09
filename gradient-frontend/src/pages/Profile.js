import React, { useEffect, useRef, useState } from 'react';
import styled from 'styled-components';
import { FiCamera, FiEye, FiEyeOff, FiCheck, FiX } from 'react-icons/fi';
import userAvatar from '../assets/user.jpg';
import {
  getMyProfile,
  setAuthToken,
  updateMyUsername,
  updateMyEmail,
  updateMyPassword,
  updateMyAvatar,
  resolveAvatarUrl,
} from '../api/client';
import { useAuth } from '../context/AuthContext';

// ---------------------------------------------------------------------------
// Styled components
// ---------------------------------------------------------------------------

const PageWrapper = styled.section`
  width: 100%;
  display: flex;
  justify-content: center;
  padding: 3rem 2rem 4.5rem;

  @media (max-width: 720px) {
    padding: 2.4rem 1.25rem 3.2rem;
  }
`;

const ProfileCard = styled.div`
  width: 100%;
  max-width: 540px;
  background: ${({ theme }) => theme.colors.cardBackground};
  border: 1px solid ${({ theme }) => theme.colors.border};
  box-shadow: 0 18px 40px ${({ theme }) => theme.colors.shadow};
  padding: 2.5rem 3rem;
  border-radius: 28px;
  display: flex;
  flex-direction: column;
  align-items: center;

  @media (max-width: 540px) {
    padding: 2.25rem 1.75rem;
  }
`;

const Title = styled.h1`
  width: 100%;
  margin: 0 0 2.5rem;
  font-size: 1.9rem;
  font-weight: 600;
  letter-spacing: 0.4px;
  text-align: left;
  color: ${({ theme }) => theme.colors.text};
`;

const AvatarBlock = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 2rem;
`;

const AvatarWrapper = styled.div`
  position: relative;
  width: 148px;
  height: 148px;
  border-radius: 50%;
  overflow: hidden;
  box-shadow: 0 0 0 4px ${({ theme }) => theme.colors.surface}, 0 18px 32px rgba(0, 0, 0, 0.18);
`;

const AvatarClickArea = styled.button`
  display: block;
  width: 100%;
  height: 100%;
  padding: 0;
  border: none;
  background: none;
  cursor: ${({ disabled }) => (disabled ? 'wait' : 'pointer')};

  &:disabled {
    opacity: 0.85;
  }
`;

const AvatarImage = styled.img`
  width: 100%;
  height: 100%;
  object-fit: cover;
  pointer-events: none;
`;

const ChangeAvatarButton = styled.button`
  margin-top: 0.85rem;
  padding: 0;
  border: none;
  background: none;
  color: ${({ theme }) => theme.colors.primary};
  font-size: 0.92rem;
  font-weight: 600;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 3px;

  &:hover:not(:disabled) {
    opacity: 0.85;
  }

  &:disabled {
    opacity: 0.5;
    cursor: wait;
  }
`;

const AvatarOverlay = styled.button`
  position: absolute;
  right: 12px;
  bottom: 12px;
  width: 42px;
  height: 42px;
  border-radius: 50%;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  background: ${({ theme }) => theme.colors.primary};
  color: #fff;
  cursor: pointer;
  box-shadow: 0 8px 20px rgba(75, 163, 255, 0.35);
  transition: transform 0.2s ease;

  &:hover {
    transform: scale(1.05);
  }
`;

const Divider = styled.hr`
  width: 100%;
  border: none;
  border-top: 1px solid ${({ theme }) => theme.colors.border};
  margin: 0.5rem 0 1.75rem;
`;

const Section = styled.div`
  width: 100%;
  margin-bottom: 1.75rem;
`;

const SectionTitle = styled.h3`
  margin: 0 0 1rem;
  font-size: 1rem;
  font-weight: 600;
  color: ${({ theme }) => theme.colors.text};
  letter-spacing: 0.2px;
`;

const FieldRow = styled.div`
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
`;

const InputShell = styled.div`
  position: relative;
  flex: 1;
`;

const Input = styled.input`
  width: 100%;
  padding: 0.9rem 1.1rem;
  border-radius: 14px;
  border: 1px solid ${({ theme }) => theme.colors.border};
  background: ${({ theme }) => theme.colors.surface};
  color: ${({ theme }) => theme.colors.text};
  font-size: 1rem;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
  box-sizing: border-box;

  &:focus {
    outline: none;
    border-color: ${({ theme }) => theme.colors.primary};
    box-shadow: 0 0 0 3px rgba(75, 163, 255, 0.25);
  }
`;

const EyeButton = styled.button`
  position: absolute;
  right: 1rem;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: ${({ theme }) => theme.colors.textSecondary};
  cursor: pointer;
`;

const SaveButton = styled.button`
  padding: 0.9rem 1.5rem;
  border-radius: 14px;
  border: none;
  background: linear-gradient(135deg, ${({ theme }) => theme.colors.primary} 0%, #7b6bff 100%);
  color: #fff;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  box-shadow: 0 8px 20px rgba(75, 163, 255, 0.28);
  transition: transform 0.2s ease, box-shadow 0.2s ease, opacity 0.2s ease;

  &:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 12px 26px rgba(75, 163, 255, 0.38);
  }

  &:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
`;

const FeedbackBadge = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  margin-top: 0.6rem;
  padding: 0.4rem 0.85rem;
  border-radius: 999px;
  font-size: 0.85rem;
  font-weight: 500;
  color: ${({ $error }) => ($error ? '#ff4d4f' : '#16db65')};
  background: ${({ $error }) =>
    $error ? 'rgba(255, 77, 79, 0.14)' : 'rgba(22, 219, 101, 0.12)'};
`;

const PasswordGrid = styled.div`
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  width: 100%;
`;

// ---------------------------------------------------------------------------
// Small reusable field section
// ---------------------------------------------------------------------------

const FieldSection = ({ title, children }) => (
  <Section>
    <SectionTitle>{title}</SectionTitle>
    {children}
  </Section>
);

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

const Profile = () => {
  const fileInputRef = useRef(null);
  const { user, setUser, updateUserAvatar } = useAuth();

  // --- avatar (stores relative path from API, e.g. /static/avatars/avatar_1.png) ---
  const [avatar, setAvatar] = useState(user?.avatar_url || '');
  const [avatarLoading, setAvatarLoading] = useState(false);
  const [avatarFeedback, setAvatarFeedback] = useState(null); // {msg, error}

  // --- username ---
  const [username, setUsername] = useState('');
  const [usernameLoading, setUsernameLoading] = useState(false);
  const [usernameFeedback, setUsernameFeedback] = useState(null);

  // --- email ---
  const [email, setEmail] = useState('');
  const [emailLoading, setEmailLoading] = useState(false);
  const [emailFeedback, setEmailFeedback] = useState(null);

  // --- password ---
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [showOld, setShowOld] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [passwordLoading, setPasswordLoading] = useState(false);
  const [passwordFeedback, setPasswordFeedback] = useState(null);

  // Load profile on mount
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const profile = await getMyProfile();
        if (cancelled || !profile) return;
        setUsername(profile.username || '');
        setEmail(profile.email || '');
        setAvatar(profile.avatar_url || '');
      } catch {
        // silently ignore — user can still edit
      }
    };
    load();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (user?.avatar_url !== undefined) {
      setAvatar(user.avatar_url || '');
    }
  }, [user?.avatar_url]);

  // --- Avatar handlers ---
  const triggerFilePicker = () => fileInputRef.current?.click();

  const handleAvatarChange = async event => {
    const file = event.target.files?.[0];
    if (!file) return;

    const previewUrl = URL.createObjectURL(file);
    setAvatar(previewUrl);
    setAvatarLoading(true);
    setAvatarFeedback(null);

    try {
      const result = await updateMyAvatar(file);
      const savedUrl = result?.avatar_url || '';
      setAvatar(savedUrl);
      updateUserAvatar(savedUrl);
      setAvatarFeedback({ msg: 'Фото оновлено', error: false });
    } catch (err) {
      setAvatar(user?.avatar_url || '');
      setAvatarFeedback({ msg: err?.message || 'Помилка оновлення фото', error: true });
    } finally {
      URL.revokeObjectURL(previewUrl);
      setAvatarLoading(false);
      event.target.value = '';
    }
  };

  // --- Username handler ---
  const handleSaveUsername = async e => {
    e.preventDefault();
    if (!username.trim()) return;
    setUsernameLoading(true);
    setUsernameFeedback(null);
    try {
      const result = await updateMyUsername({ username: username.trim() });
      if (result?.access_token) setAuthToken(result.access_token);
      setUser(prev => ({ ...(prev || {}), username: result?.username || username.trim() }));
      setUsernameFeedback({ msg: "Ім'я оновлено", error: false });
    } catch (err) {
      setUsernameFeedback({ msg: err?.message || 'Помилка оновлення', error: true });
    } finally {
      setUsernameLoading(false);
    }
  };

  // --- Email handler ---
  const handleSaveEmail = async e => {
    e.preventDefault();
    if (!email.trim()) return;
    setEmailLoading(true);
    setEmailFeedback(null);
    try {
      await updateMyEmail({ email: email.trim() });
      setUser(prev => ({ ...(prev || {}), email: email.trim() }));
      setEmailFeedback({ msg: 'Email оновлено', error: false });
    } catch (err) {
      setEmailFeedback({ msg: err?.message || 'Помилка оновлення', error: true });
    } finally {
      setEmailLoading(false);
    }
  };

  // --- Password handler ---
  const handleSavePassword = async e => {
    e.preventDefault();
    if (!oldPassword.trim() || !newPassword.trim()) return;
    setPasswordLoading(true);
    setPasswordFeedback(null);
    try {
      await updateMyPassword({ old_password: oldPassword.trim(), new_password: newPassword.trim() });
      setOldPassword('');
      setNewPassword('');
      setPasswordFeedback({ msg: 'Пароль змінено', error: false });
    } catch (err) {
      setPasswordFeedback({ msg: err?.message || 'Помилка зміни пароля', error: true });
    } finally {
      setPasswordLoading(false);
    }
  };

  return (
    <PageWrapper>
      <ProfileCard>
        <Title>Профіль</Title>

        {/* Avatar */}
        <AvatarBlock>
          <AvatarWrapper>
            <AvatarClickArea
              type="button"
              onClick={triggerFilePicker}
              disabled={avatarLoading}
              title="Змінити аватар"
              aria-label="Змінити аватар"
            >
              <AvatarImage
                key={avatar || user?.avatar_url || 'default'}
                src={resolveAvatarUrl(avatar || user?.avatar_url) || userAvatar}
                alt="Аватар користувача"
              />
            </AvatarClickArea>
            <AvatarOverlay
              type="button"
              onClick={triggerFilePicker}
              title="Оновити фото"
              disabled={avatarLoading}
              aria-label="Оновити фото"
            >
              <FiCamera size={18} />
            </AvatarOverlay>
          </AvatarWrapper>
          <ChangeAvatarButton
            type="button"
            onClick={triggerFilePicker}
            disabled={avatarLoading}
          >
            {avatarLoading ? 'Завантаження...' : 'Змінити аватар'}
          </ChangeAvatarButton>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            onChange={handleAvatarChange}
            style={{ display: 'none' }}
            aria-hidden="true"
          />
          {avatarFeedback && (
            <FeedbackBadge $error={avatarFeedback.error} style={{ marginTop: '0.65rem' }}>
              {avatarFeedback.error ? <FiX size={13} /> : <FiCheck size={13} />}
              {avatarFeedback.msg}
            </FeedbackBadge>
          )}
        </AvatarBlock>

        <Divider style={{ marginTop: '1.5rem' }} />

        {/* Username */}
        <FieldSection title="Імʼя">
          <form onSubmit={handleSaveUsername}>
            <FieldRow>
              <InputShell>
                <Input
                  type="text"
                  value={username}
                  onChange={e => { setUsername(e.target.value); setUsernameFeedback(null); }}
                  placeholder="Введіть ім'я"
                  autoComplete="name"
                  required
                />
              </InputShell>
              <SaveButton type="submit" disabled={usernameLoading || !username.trim()}>
                {usernameLoading ? '...' : 'Зберегти'}
              </SaveButton>
            </FieldRow>
            {usernameFeedback && (
              <FeedbackBadge $error={usernameFeedback.error}>
                {usernameFeedback.error ? <FiX size={13} /> : <FiCheck size={13} />}
                {usernameFeedback.msg}
              </FeedbackBadge>
            )}
          </form>
        </FieldSection>

        {/* Email */}
        <FieldSection title="Email">
          <form onSubmit={handleSaveEmail}>
            <FieldRow>
              <InputShell>
                <Input
                  type="email"
                  value={email}
                  onChange={e => { setEmail(e.target.value); setEmailFeedback(null); }}
                  placeholder="email@example.com"
                  autoComplete="email"
                  required
                />
              </InputShell>
              <SaveButton type="submit" disabled={emailLoading || !email.trim()}>
                {emailLoading ? '...' : 'Зберегти'}
              </SaveButton>
            </FieldRow>
            {emailFeedback && (
              <FeedbackBadge $error={emailFeedback.error}>
                {emailFeedback.error ? <FiX size={13} /> : <FiCheck size={13} />}
                {emailFeedback.msg}
              </FeedbackBadge>
            )}
          </form>
        </FieldSection>

        {/* Password */}
        <FieldSection title="Зміна пароля">
          <form onSubmit={handleSavePassword}>
            <PasswordGrid>
              <InputShell>
                <Input
                  type={showOld ? 'text' : 'password'}
                  value={oldPassword}
                  onChange={e => { setOldPassword(e.target.value); setPasswordFeedback(null); }}
                  placeholder="Старий пароль"
                  autoComplete="current-password"
                  required
                />
                <EyeButton
                  type="button"
                  onClick={() => setShowOld(v => !v)}
                  title={showOld ? 'Сховати' : 'Показати'}
                >
                  {showOld ? <FiEyeOff size={18} /> : <FiEye size={18} />}
                </EyeButton>
              </InputShell>

              <InputShell>
                <Input
                  type={showNew ? 'text' : 'password'}
                  value={newPassword}
                  onChange={e => { setNewPassword(e.target.value); setPasswordFeedback(null); }}
                  placeholder="Новий пароль (мін. 6 символів)"
                  autoComplete="new-password"
                  minLength={6}
                  required
                />
                <EyeButton
                  type="button"
                  onClick={() => setShowNew(v => !v)}
                  title={showNew ? 'Сховати' : 'Показати'}
                >
                  {showNew ? <FiEyeOff size={18} /> : <FiEye size={18} />}
                </EyeButton>
              </InputShell>

              <SaveButton
                type="submit"
                disabled={passwordLoading || !oldPassword.trim() || !newPassword.trim()}
                style={{ alignSelf: 'flex-start' }}
              >
                {passwordLoading ? 'Збереження...' : 'Змінити пароль'}
              </SaveButton>
            </PasswordGrid>
            {passwordFeedback && (
              <FeedbackBadge $error={passwordFeedback.error}>
                {passwordFeedback.error ? <FiX size={13} /> : <FiCheck size={13} />}
                {passwordFeedback.msg}
              </FeedbackBadge>
            )}
          </form>
        </FieldSection>
      </ProfileCard>
    </PageWrapper>
  );
};

export default Profile;
