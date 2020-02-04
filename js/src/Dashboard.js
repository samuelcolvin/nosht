import React from 'react'
import {Route, Switch, Link} from 'react-router-dom'
import {Nav, NavItem} from 'reactstrap'
import {NotFound} from './general/Errors'
import WithContext from './utils/context'
import {as_title} from './utils'
import {EventsList, EventsDetails} from './events/Dashboard'
import {UsersList, UsersDetails} from './users/Dashboard'
import Account from './users/Account'
import {CategoriesList, CategoriesDetails} from './cats/Dashboard'
import {EmailDefList, EmailDefDetails} from './emails/Dashboard'
import {DonationOptionsList, DonationOptionDetails} from './donations/Dashboard'
import CompanyDetails from './company/Dashboard'
import Export from './Export'

const list_uri = page => `/dashboard/${page.name}/`
const list_match_uri = page => `/dashboard/${page.name}/(add/)?`
const details_uri = page => page.details_uri || `/dashboard/${page.name}/:id/`

const MenuItem = ({page, location}) => {
  const uri = list_uri(page)
  const active = location.pathname.startsWith(uri) ? ' active' : ''
  return (
    <NavItem>
      <NavItem tag={Link} to={uri} className={'nav-link' + active}>
        {page.title || as_title(page.name)}
      </NavItem>
    </NavItem>
  )
}

class Dashboard extends React.Component {
  componentDidMount () {
    this.props.ctx.setRootState({active_page: 'dashboard'})
  }

  render () {
    let pages = [
      {name: 'events', title: 'My Events', list_comp: EventsList, details_comp: EventsDetails},
    ]
    if (this.props.ctx.user && this.props.ctx.user.role === 'admin') {
      pages = [
        {name: 'events', list_comp: EventsList, details_comp: EventsDetails},
        {name: 'categories', list_comp: CategoriesList, details_comp: CategoriesDetails},
        {name: 'users', list_comp: UsersList, details_comp: UsersDetails},
        {name: 'company', details_comp: CompanyDetails, details_uri: '/dashboard/company/'},
        {name: 'email-defs', list_comp: EmailDefList, details_comp: EmailDefDetails, title: 'Emails'},
        {name: 'donation-options', list_comp: DonationOptionsList, details_comp: DonationOptionDetails},
        {name: 'export', details_comp: Export, details_uri: '/dashboard/export/'},
      ]
    }
    pages.push(
      {name: 'account', title: 'Account', details_comp: Account, details_uri: '/dashboard/account/'}
    )
    return (
      <div>
        <Nav pills className="mb-2">
          {pages.map(p => (
            <MenuItem key={p.name} page={p} location={this.props.location}/>
          ))}
        </Nav>
        <hr className="full-width"/>
        <Switch>
          {pages.filter(p => p.list_comp).map(p => (
            <Route key={p.name} exact path={list_match_uri(p)} render={props => {
              const Comp = p.list_comp
              return <Comp ctx={this.props.ctx} {...props} page={p}/>
            }}/>
          ))}
          {pages.filter(p => p.details_comp).map(p => (
            <Route key={p.name + '-details'} path={details_uri(p)} render={props => {
              const Comp = p.details_comp
              return <Comp ctx={this.props.ctx} {...props} page={p}/>
            }}/>
          ))}

          <Route component={NotFound}/>
        </Switch>
      </div>
    )
  }
}
export default WithContext(Dashboard)
