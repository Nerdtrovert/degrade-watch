// src/components/ui/Button.tsx
import React from 'react';

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  disabled?: boolean;
  children: React.ReactNode;
};

const variantClasses: Record<NonNullable<ButtonProps['variant']>, string> = {
  primary: 'bg-primary text-surface hover:bg-primary-hover active:bg-primary-active disabled:opacity-50',
  secondary: 'bg-gray-200 text-text-primary hover:bg-gray-300 disabled:opacity-50',
  danger: 'bg-danger text-surface hover:bg-danger/90 disabled:opacity-50',
  ghost: 'bg-transparent border border-border text-text-primary hover:bg-gray-100 disabled:opacity-50',
};

export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  disabled = false,
  children,
  className = '',
  ...rest
}) => {
  const classes = `inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-medium transition-colors ${variantClasses[variant]} ${className}`;
  return (
    <button className={classes} disabled={disabled} {...rest}>
      {children}
    </button>
  );
};
