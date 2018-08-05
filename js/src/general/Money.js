import React from 'react'
import WithContext from '../utils/context'

export const currency_lookup = {
  gbp: '£',
  usd: '$',
  eur: '€',
}

export const format_money = (currency, money) => (
  currency_lookup[currency] + (money || 0).toFixed(2)
)

export const format_money_free = (currency, money) => (
  money ? format_money(currency, money) : 'Free'
)

export const Money = WithContext(({ctx, children}) => (
  <span>{format_money(ctx.company.company.currency, children || 0)}</span>
))

export const MoneyFree = WithContext(({ctx, children}) => (
  <span>{format_money_free(ctx.company.company.currency, children)}</span>
))
