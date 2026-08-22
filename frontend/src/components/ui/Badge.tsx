// src/components/ui/Badge.tsx
import React from 'react';

type BadgeProps = React.HTMLAttributes<HTMLSpanElement> & {
  variant?: 'normal' | 'suspicious' | 'incident' | 'auto_approved' | 'human_approval' | 'blocked';
  children: React.ReactNode;
};

const variantClasses: Record<NonNullable<BadgeProps['variant']>, string> = {
  normal: 'bg-success text-white',
  suspicious: 'bg-warning text-white',
  incident: 'bg-critical text-white',
  auto_approved: 'bg-success text-white',
  human_approval: 'bg-warning text-white',
  blocked: 'bg-critical text-white',
};

export const Badge: React.FC<BadgeProps> = ({
  variant = 'normal',
  children,
  className = '',
  ...rest
}) => {
  const classes = `inline-flex items-center rounded-sm px-2 py-0.5 text-xs font-medium ${variantClasses[variant]} ${className}`;
  return (
    <span className={classes} {...rest}>
      {children}
    </span>
  );
};
