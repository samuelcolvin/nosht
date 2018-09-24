import React from 'react'
import WithContext from '../utils/context'

export const currency_lookup = {
  gbp: '£',
  usd: '$',
  eur: '€',
}

export const format_money = (currency, money, NoSymbol) => {
  const v = (money || 0).toFixed(2)
  return NoSymbol ? v : currency_lookup[currency] + v
}

export const format_money_free = (currency, money, NoSymbol) => (
  money ? format_money(currency, money, NoSymbol) : 'Free'
)

export const Money = WithContext(({ctx, children}) => (
  <span>{format_money(ctx.company.company.currency, children || 0)}</span>
))

export const MoneyFree = WithContext(({ctx, children, NoSymbol}) => (
  <span>{format_money_free(ctx.company.company.currency, children, NoSymbol)}</span>
))
