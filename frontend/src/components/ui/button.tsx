import React from 'react';

type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'default' | 'outline';
  size?: 'sm' | 'md' | 'lg';
};

export function Button({
  className = '',
  variant = 'default',
  size = 'md',
  children,
  ...rest
}: Props) {
  const base =
    'inline-flex items-center justify-center rounded-md font-medium focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none';
  const variants: Record<string, string> = {
    default: 'bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500',
    outline: 'border border-gray-300 text-gray-700 bg-white hover:bg-gray-50 focus:ring-blue-500',
  };
  const sizes: Record<string, string> = {
    sm: 'h-8 px-2 text-sm',
    md: 'h-9 px-3 text-sm',
    lg: 'h-10 px-4 text-base',
  };
  return (
    <button className={`${base} ${variants[variant]} ${sizes[size]} ${className}`} {...rest}>
      {children}
    </button>
  );
}
