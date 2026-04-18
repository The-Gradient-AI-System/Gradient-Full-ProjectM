import React, { useEffect, useState } from 'react';
import styled, { keyframes } from 'styled-components';
import { FiMail, FiLock, FiArrowRight, FiEye, FiEyeOff } from 'react-icons/fi';
import { FcGoogle } from 'react-icons/fc';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const blurPulse = keyframes`
  0% {
    transform: translate(-50%, -50%) scale(1);
    opacity: 0.55;
  }
  50% {
    transform: translate(-50%, -50%) scale(1.08);
    opacity: 0.8;
  }
  100% {
    transform: translate(-50%, -50%) scale(1);
    opacity: 0.55;
  }
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
  width: min(100%, 420px);
  padding: clamp(2.4rem, 5vw, 3rem);
  border-radius: 28px;
  background: ${({ theme }) => theme.colors.surface};
  border: 1px solid ${({ theme }) => theme.colors.border};
  box-shadow: 0 26px 65px rgba(15, 23, 42, 0.18);
  display: flex;
  flex-direction: column;
  gap: 2rem;
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
    font-size: clamp(1.9rem, 3vw, 2.3rem);
    font-weight: 600;
    letter-spacing: 0.3px;
    line-height: 1.2;
  }

  p {
    margin: 0;
    color: ${({ theme }) => theme.colors.textSecondary};
    font-size: 0.98rem;
  }
`;

const Form = styled.form`
  display: flex;
  flex-direction: column;
  gap: 1.45rem;
`;

const Field = styled.label`
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
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
  transition: transform 0.2s ease, box-shadow 0.2s ease;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 14px 32px rgba(75, 163, 255, 0.28);
  }
`;

const SecondaryButton = styled.button`
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  width: 100%;
  padding: 0.9rem 1.5rem;
  border-radius: 16px;
  border: 1px solid ${({ theme }) => theme.colors.border};
  background: ${({ theme }) => theme.colors.surface};
  color: ${({ theme }) => theme.colors.text};
  font-weight: 500;
  font-size: 0.98rem;
  cursor: pointer;
  transition: background 0.2s ease, transform 0.2s ease, border-color 0.2s ease;

  &:hover {
    background: ${({ theme }) => theme.colors.hover};
    transform: translateY(-1px);
    border-color: ${({ theme }) => theme.colors.primary};
  }
`;

const Divider = styled.div`
  display: flex;
  align-items: center;
  gap: 0.85rem;
  color: ${({ theme }) => theme.colors.textSecondary};
  font-size: 0.85rem;

  &::before,
  &::after {
    content: '';
    flex: 1;
    height: 1px;
    background: ${({ theme }) => theme.colors.border};
  }
`;

const Helper = styled.p`
  margin: 0;
  text-align: center;
  font-size: 0.85rem;
  color: ${({ theme }) => theme.colors.textSecondary};
`;

const Message = styled.div`
  text-align: center;
  padding: 0.75rem 1rem;
  border-radius: 14px;
  background: ${({ $variant }) => ($variant === 'error' ? 'rgba(255, 77, 79, 0.15)' : 'rgba(52, 211, 153, 0.18)')};
  color: ${({ $variant }) => ($variant === 'error' ? '#ff4d4f' : '#16db65')};
  font-size: 0.9rem;
  font-weight: 500;
`;

const Login = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const { login, loading, error, clearError, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (isAuthenticated) {
      navigate('/', { replace: true });
    }
  }, [isAuthenticated, navigate]);

  const onSubmit = async event => {
    event.preventDefault();
    const result = await login({ email, password });
    if (result.success) {
      navigate('/', { replace: true });
    }
  };

  const handleEmailChange = event => {
    if (error) clearError();
    setEmail(event.target.value);
  };

  const handlePasswordChange = event => {
    if (error) clearError();
    setPassword(event.target.value);
  };

  return (
    <Background>
      <Card>
        <TitleBlock>
          <h1>Ласкаво просимо назад</h1>
          <p>Увійдіть, щоб керувати аналітикою, автоматизацією та профілями контактів.</p>
        </TitleBlock>

        <Form onSubmit={onSubmit}>
          <Field>
            Email адреса
            <InputShell>
              <InputIcon>
                <FiMail />
              </InputIcon>
              <Input
                type="email"
                placeholder="name@company.com"
                value={email}
                onChange={handleEmailChange}
                required
              />
            </InputShell>
          </Field>

          <Field>
            Пароль
            <InputShell>
              <InputIcon>
                <FiLock />
              </InputIcon>
              <Input
                type={showPassword ? 'text' : 'password'}
                placeholder="••••••••"
                value={password}
                onChange={handlePasswordChange}
                minLength={6}
                required
              />
              <ToggleVisibility
                type="button"
                onClick={() => setShowPassword(prev => !prev)}
                aria-label={showPassword ? 'Сховати пароль' : 'Показати пароль'}
              >
                {showPassword ? <FiEyeOff /> : <FiEye />}
              </ToggleVisibility>
            </InputShell>
          </Field>

          <PrimaryButton type="submit" disabled={loading}>
            {loading ? 'Входимо…' : 'Увійти'}
            {!loading && <FiArrowRight />}
          </PrimaryButton>
        </Form>

        <Divider>або</Divider>

        <SecondaryButton type="button">
          <FcGoogle size={20} />
          Увійти через Google
        </SecondaryButton>

        <Helper>Справжня авторизація з'явиться після підключення бекенду.</Helper>
        {error && <Message $variant="error">{error}</Message>}
      </Card>
    </Background>
  );
};

export default Login;
