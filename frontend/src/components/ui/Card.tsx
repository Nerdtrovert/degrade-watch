// src/components/ui/Card.tsx
import React from 'react';

type CardProps = React.HTMLAttributes<HTMLDivElement> & {
  children: React.ReactNode;
};

export const Card: React.FC<CardProps> = ({ children, className = '', ...rest }) => {
  const classes = `bg-surface border border-border rounded-md p-4 shadow-subtle ${className}`;
  return (
    <div className={classes} {...rest}>
      {children}
    </div>
  );
};
