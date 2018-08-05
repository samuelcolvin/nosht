import React from 'react'
import {Route, Switch, Link} from 'react-router-dom'
import {Row, Col} from 'reactstrap'
import {NotFound} from './general/Errors'
import WithContext from './utils/context'
import {as_title} from './utils'
import {EventsList, EventsDetails} from './events/Dashboard'
import {UsersList, UsersDetails} from './users/Dashboard'
import {CategoriesList, CategoriesDetails} from './cats/Dashboard'
import CompanyDetails from './company/Dashboard'

const list_uri = page => `/dashboard/${page.name}/`
const list_match_uri = page => `/dashboard/${page.name}/(add/)?`
const details_uri = page => page.details_uri || `/dashboard/${page.name}/:id/`

const MenuItem = ({page, location}) => {
  const uri = list_uri(page)
  const active = location.pathname.startsWith(uri) ? ' active' : ''
  return <Link to={uri} className={'list-group-item list-group-item-action' + active}>
    {page.title || as_title(page.name)}
  </Link>
}

class Dashboard extends React.Component {
  render () {
    let pages = [
      {name: 'events', title: 'My Events', list_comp: EventsList, details_comp: EventsDetails},
      {name: 'account', title: 'Account', list_comp: null, details_comp: null},
    ]
    if (this.props.ctx.user && this.props.ctx.user.role === 'admin') {
      pages = [
        {name: 'events', list_comp: EventsList, details_comp: EventsDetails},
        {name: 'categories', list_comp: CategoriesList, details_comp: CategoriesDetails},
        {name: 'users', list_comp: UsersList, details_comp: UsersDetails},
        {name: 'company', list_comp: null, details_comp: CompanyDetails, details_uri: '/dashboard/company/'},
        {name: 'export', list_comp: null, details_comp: null},
      ]
    }
    return (
      <Row>
        <Col md="3">
        <div className="list-group mb-2">
          {pages.map(p => (
            <MenuItem key={p.name} page={p} location={this.props.location}/>
          ))}
        </div>
        </Col>
        <Col md="9">
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

        </Col>
      </Row>
    )
  }
}
export default WithContext(Dashboard)
