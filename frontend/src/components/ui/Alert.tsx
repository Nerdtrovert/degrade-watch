// src/components/ui/Alert.tsx
import React from 'react';

type AlertProps = React.HTMLAttributes<HTMLDivElement> & {
  variant?: 'success' | 'warning' | 'critical' | 'info';
  title?: string;
  children: React.ReactNode;
};

const variantClasses: Record<NonNullable<AlertProps['variant']>, string> = {
  success: 'bg-success text-white border border-success',
  warning: 'bg-warning text-white border border-warning',
  critical: 'bg-critical text-white border border-critical',
  info: 'bg-info text-white border border-info',
};

export const Alert: React.FC<AlertProps> = ({
  variant = 'info',
  title,
  children,
  className = '',
  ...rest
}) => {
  const classes = `p-4 rounded-md ${variantClasses[variant]} ${className}`;
  return (
    <div className={classes} {...rest}>
      {title && <div className="font-medium mb-2">{title}</div>}
      <div>{children}</div>
    </div>
  );
};
