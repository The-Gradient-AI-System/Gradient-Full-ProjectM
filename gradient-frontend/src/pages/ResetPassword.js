import React, { useState } from 'react';
import styled, { keyframes } from 'styled-components';
import { FiMail, FiLock, FiHash, FiArrowLeft, FiEye, FiEyeOff, FiArrowRight } from 'react-icons/fi';
import { useNavigate, useLocation } from 'react-router-dom';
import { forgotPassword, resetPassword } from '../api/client';

// ---------------------------------------------------------------------------
// Styled components (reuse Login visual style)
// ---------------------------------------------------------------------------

const blurPulse = keyframes`
  0%   { transform: translate(-50%, -50%) scale(1);    opacity: 0.55; }
  50%  { transform: translate(-50%, -50%) scale(1.08); opacity: 0.8;  }
  100% { transform: translate(-50%, -50%) scale(1);    opacity: 0.55; }
`;

const Background = styled.section`
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4rem clamp(1.5rem, 4vw, 5rem);
  background: radial-gradient(circle at top left, rgba(123, 107, 255, 0.22), transparent 55%),
    radial-gradient(circle at bottom right, rgba(75, 163, 255, 0.18), transparent 52%),
    ${({ theme }) => theme.colors.background};
  position: relative;
  overflow: hidden;

  &::before,
  &::after {
    content: '';
    position: absolute;
    border-radius: 50%;
    filter: blur(110px);
    opacity: 0.65;
    pointer-events: none;
  }

  &::before {
    width: 520px;
    height: 520px;
    top: 15%;
    left: 18%;
    background: linear-gradient(135deg, rgba(75, 163, 255, 0.6), rgba(123, 107, 255, 0.3));
    animation: ${blurPulse} 7.5s ease-in-out infinite;
  }

  &::after {
    width: 440px;
    height: 440px;
    bottom: -12%;
    right: 12%;
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.22), rgba(75, 163, 255, 0.18));
  }
`;

const Card = styled.div`
  position: relative;
  width: min(100%, 440px);
  padding: clamp(2.4rem, 5vw, 3rem);
  border-radius: 28px;
  background: ${({ theme }) => theme.colors.surface};
  border: 1px solid ${({ theme }) => theme.colors.border};
  box-shadow: 0 26px 65px rgba(15, 23, 42, 0.18);
  display: flex;
  flex-direction: column;
  gap: 1.75rem;
  z-index: 1;

  @media (max-width: 520px) {
    padding: 2.5rem 1.75rem;
    border-radius: 22px;
  }
`;

const TitleBlock = styled.header`
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  color: ${({ theme }) => theme.colors.text};

  h1 {
    font-size: clamp(1.7rem, 3vw, 2.1rem);
    font-weight: 600;
    letter-spacing: 0.3px;
    line-height: 1.2;
    margin: 0;
  }

  p {
    margin: 0;
    color: ${({ theme }) => theme.colors.textSecondary};
    font-size: 0.95rem;
    line-height: 1.5;
  }
`;

const Form = styled.form`
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
`;

const Field = styled.label`
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  font-size: 0.9rem;
  color: ${({ theme }) => theme.colors.textSecondary};
`;

const InputShell = styled.div`
  position: relative;
`;

const Input = styled.input`
  width: 100%;
  padding: 0.95rem 1rem 0.95rem 2.6rem;
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
    box-shadow: 0 0 0 3px rgba(75, 163, 255, 0.2);
  }
`;

const InputIcon = styled.span`
  position: absolute;
  top: 50%;
  left: 1rem;
  transform: translateY(-50%);
  color: ${({ theme }) => theme.colors.textSecondary};
  font-size: 1.1rem;
  pointer-events: none;
`;

const ToggleVisibility = styled.button`
  position: absolute;
  top: 50%;
  right: 1rem;
  transform: translateY(-50%);
  border: none;
  background: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: ${({ theme }) => theme.colors.textSecondary};
  font-size: 1.05rem;
  cursor: pointer;
  padding: 0;

  &:hover {
    color: ${({ theme }) => theme.colors.text};
  }
`;

const PrimaryButton = styled.button`
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.6rem;
  width: 100%;
  padding: 0.95rem 1.5rem;
  border-radius: 16px;
  border: none;
  background: linear-gradient(135deg, ${({ theme }) => theme.colors.primary}, #7b6bff);
  color: #fff;
  font-size: 1.05rem;
  font-weight: 600;
  letter-spacing: 0.4px;
  cursor: pointer;
  box-shadow: 0 12px 26px rgba(75, 163, 255, 0.22);
  transition: transform 0.2s ease, box-shadow 0.2s ease, opacity 0.2s ease;

  &:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 14px 32px rgba(75, 163, 255, 0.28);
  }

  &:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
`;

const BackLink = styled.button`
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  background: none;
  border: none;
  color: ${({ theme }) => theme.colors.textSecondary};
  font-size: 0.9rem;
  cursor: pointer;
  padding: 0;
  transition: color 0.2s ease;

  &:hover {
    color: ${({ theme }) => theme.colors.text};
  }
`;

const Message = styled.div`
  text-align: center;
  padding: 0.75rem 1rem;
  border-radius: 14px;
  background: ${({ $variant }) =>
    $variant === 'error' ? 'rgba(255, 77, 79, 0.15)' : 'rgba(52, 211, 153, 0.18)'};
  color: ${({ $variant }) => ($variant === 'error' ? '#ff4d4f' : '#16db65')};
  font-size: 0.9rem;
  font-weight: 500;
`;

const HintText = styled.p`
  margin: 0;
  font-size: 0.82rem;
  color: ${({ theme }) => theme.colors.textSecondary};
  line-height: 1.5;
`;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const STEP_EMAIL = 'email';   // enter email to request code
const STEP_RESET = 'reset';   // enter code + new password

const ResetPassword = () => {
  const navigate = useNavigate();
  const location = useLocation();

  // Pre-fill email if passed via navigation state from Login
  const [email, setEmail] = useState(location.state?.email || '');
  const [step, setStep] = useState(STEP_EMAIL);

  // Step 1
  const [requestLoading, setRequestLoading] = useState(false);
  const [requestMsg, setRequestMsg] = useState(null); // {text, error}

  // Step 2
  const [code, setCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [resetLoading, setResetLoading] = useState(false);
  const [resetMsg, setResetMsg] = useState(null); // {text, error}
  const [done, setDone] = useState(false);

  // --- Step 1: request code ---
  const handleRequestCode = async e => {
    e.preventDefault();
    setRequestLoading(true);
    setRequestMsg(null);
    try {
      await forgotPassword({ email: email.trim() });
      setRequestMsg({
        text: 'Якщо цей email зареєстровано — код надіслано. Перевірте пошту.',
        error: false,
      });
      // Move to step 2 after a short delay so user reads the message
      setTimeout(() => setStep(STEP_RESET), 1800);
    } catch (err) {
      setRequestMsg({ text: err?.message || 'Помилка. Спробуйте ще раз.', error: true });
    } finally {
      setRequestLoading(false);
    }
  };

  // --- Step 2: submit code + new password ---
  const handleResetPassword = async e => {
    e.preventDefault();
    setResetLoading(true);
    setResetMsg(null);
    try {
      await resetPassword({
        email: email.trim(),
        code: code.trim(),
        new_password: newPassword.trim(),
      });
      setDone(true);
      setResetMsg({ text: 'Пароль успішно змінено! Перенаправляємо...', error: false });
      setTimeout(() => navigate('/login', { replace: true }), 2500);
    } catch (err) {
      setResetMsg({ text: err?.message || 'Невірний або прострочений код.', error: true });
    } finally {
      setResetLoading(false);
    }
  };

  return (
    <Background>
      <Card>
        <BackLink type="button" onClick={() => navigate('/login')}>
          <FiArrowLeft size={15} />
          Назад до входу
        </BackLink>

        {step === STEP_EMAIL ? (
          <>
            <TitleBlock>
              <h1>Скидання пароля</h1>
              <p>
                Введіть email вашого акаунта. Ми надішлемо 6-значний код для підтвердження.
              </p>
            </TitleBlock>

            <Form onSubmit={handleRequestCode}>
              <Field>
                Email адреса
                <InputShell>
                  <InputIcon><FiMail /></InputIcon>
                  <Input
                    type="email"
                    placeholder="name@company.com"
                    value={email}
                    onChange={e => { setEmail(e.target.value); setRequestMsg(null); }}
                    required
                    autoFocus
                  />
                </InputShell>
              </Field>

              <PrimaryButton type="submit" disabled={requestLoading || !email.trim()}>
                {requestLoading ? 'Надсилаємо...' : 'Надіслати код'}
                {!requestLoading && <FiArrowRight />}
              </PrimaryButton>
            </Form>

            {requestMsg && (
              <Message $variant={requestMsg.error ? 'error' : 'success'}>
                {requestMsg.text}
              </Message>
            )}
          </>
        ) : (
          <>
            <TitleBlock>
              <h1>Введіть код</h1>
              <p>
                Код надіслано на <strong>{email}</strong>. Він дійсний 10 хвилин.
              </p>
            </TitleBlock>

            <Form onSubmit={handleResetPassword}>
              <Field>
                Код підтвердження
                <InputShell>
                  <InputIcon><FiHash /></InputIcon>
                  <Input
                    type="text"
                    placeholder="123456"
                    value={code}
                    onChange={e => { setCode(e.target.value); setResetMsg(null); }}
                    maxLength={10}
                    required
                    autoFocus
                    disabled={done}
                  />
                </InputShell>
              </Field>

              <Field>
                Новий пароль
                <InputShell>
                  <InputIcon><FiLock /></InputIcon>
                  <Input
                    type={showPassword ? 'text' : 'password'}
                    placeholder="Мінімум 6 символів"
                    value={newPassword}
                    onChange={e => { setNewPassword(e.target.value); setResetMsg(null); }}
                    minLength={6}
                    required
                    disabled={done}
                  />
                  <ToggleVisibility
                    type="button"
                    onClick={() => setShowPassword(v => !v)}
                    aria-label={showPassword ? 'Сховати пароль' : 'Показати пароль'}
                  >
                    {showPassword ? <FiEyeOff /> : <FiEye />}
                  </ToggleVisibility>
                </InputShell>
              </Field>

              <HintText>
                Не отримали код?{' '}
                <BackLink
                  type="button"
                  style={{ fontSize: '0.82rem', display: 'inline' }}
                  onClick={() => { setStep(STEP_EMAIL); setResetMsg(null); }}
                >
                  Надіслати ще раз
                </BackLink>
              </HintText>

              <PrimaryButton
                type="submit"
                disabled={resetLoading || !code.trim() || !newPassword.trim() || done}
              >
                {resetLoading ? 'Перевіряємо...' : 'Змінити пароль'}
                {!resetLoading && <FiArrowRight />}
              </PrimaryButton>
            </Form>

            {resetMsg && (
              <Message $variant={resetMsg.error ? 'error' : 'success'}>
                {resetMsg.text}
              </Message>
            )}
          </>
        )}
      </Card>
    </Background>
  );
};

export default ResetPassword;
