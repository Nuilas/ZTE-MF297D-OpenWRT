// SPDX-License-Identifier: GPL-2.0-only
/* MF297D NSS-owned IPv4 TSO companion. The firmware/GMAC rings are untouched.
 * RTNL serializes attachment, restoration and netdevice removal. No netdevice
 * reference is retained across RTNL, so bridge removal cannot wait on us.
 */
#include <linux/module.h>
#include <linux/netdevice.h>
#include <linux/rtnetlink.h>
#include <linux/of.h>
#include <linux/workqueue.h>
#include <linux/if_vlan.h>
#include <net/net_namespace.h>
#include "stmmac.h"

#define TSO_MASK (NETIF_F_TSO | NETIF_F_IP_CSUM | NETIF_F_SG)
struct saved_port {
 const char *name;
 bool route_only;
 struct net_device *dev;
 netdev_features_t features,hw,vlan,wanted;
 unsigned int ipv4_max;
};
static char *bridge_name="br-lan";
module_param(bridge_name,charp,0400);
static struct saved_port ports[]={{.name="eth0"},{.name="lan1"},{.route_only=true}};
static const struct net_device_ops *original_ops;
static struct net_device_ops tso_ops;
static const struct qca_dwmac_dp_owner *owner;
static bool ready,enabled;
static unsigned int seconds=10;
module_param(seconds,uint,0400);
MODULE_PARM_DESC(seconds,"Rollback seconds (1-30); 0 explicitly selects persistent operation");
static atomic64_t gso_packets=ATOMIC64_INIT(0);
static atomic64_t gso_bytes=ATOMIC64_INIT(0);
static void rollback_fn(struct work_struct *work);
static DECLARE_DELAYED_WORK(rollback_work,rollback_fn);

static netdev_features_t tso_features_check(struct sk_buff *skb,
 struct net_device *dev,netdev_features_t features)
{
 struct stmmac_priv *priv=netdev_priv(dev);
 if(READ_ONCE(enabled) && owner && READ_ONCE(priv->dp_owner)==owner &&
    skb_is_gso(skb) && !skb->encapsulation &&
    (skb_shinfo(skb)->gso_type&SKB_GSO_TCPV4)){
  netdev_features_t allowed=vlan_features_check(skb,features);
  if(allowed&NETIF_F_TSO){
   atomic64_inc(&gso_packets);atomic64_add(skb->len,&gso_bytes);
  }
  return allowed;
 }
 return original_ops->ndo_features_check ?
  original_ops->ndo_features_check(skb,dev,features) : features;
}

static void restore_rtnl(void)
{
 int i;
 ASSERT_RTNL();
 if(!enabled)return;
 WRITE_ONCE(enabled,false);
 WRITE_ONCE(ports[0].dev->netdev_ops,original_ops);
 for(i=ARRAY_SIZE(ports)-1;i>=0;i--){
  struct saved_port *p=&ports[i];struct net_device *d=p->dev;
  d->features=(d->features&~TSO_MASK)|(p->features&TSO_MASK);
  d->hw_features=(d->hw_features&~TSO_MASK)|(p->hw&TSO_MASK);
  d->vlan_features=(d->vlan_features&~TSO_MASK)|(p->vlan&TSO_MASK);
  d->wanted_features=(d->wanted_features&~TSO_MASK)|(p->wanted&TSO_MASK);
  if(READ_ONCE(d->gso_ipv4_max_size)==min_t(unsigned int,p->ipv4_max,32768))
   WRITE_ONCE(d->gso_ipv4_max_size,p->ipv4_max);
  if(d->reg_state==NETREG_REGISTERED)netdev_update_features(d);
  p->dev=NULL;
 }
 pr_info("mf297d-host-tso: restored; GSO packets=%lld bytes=%lld\n",
  (long long)atomic64_read(&gso_packets),(long long)atomic64_read(&gso_bytes));
}

static int attach_rtnl(void)
{
 unsigned int i;int ret=0;
 ASSERT_RTNL();
 if(enabled)return 0;
 for(i=0;i<ARRAY_SIZE(ports);i++){
  struct saved_port *p=&ports[i];struct net_device *d;
  d=__dev_get_by_name(&init_net,p->name);
  if(!d || d->reg_state!=NETREG_REGISTERED){ret=-ENODEV;goto fail;}
  p->dev=d;p->features=d->features;p->hw=d->hw_features;
  p->vlan=d->vlan_features;p->wanted=d->wanted_features;
  p->ipv4_max=READ_ONCE(d->gso_ipv4_max_size);
  if(p->ipv4_max<32768){ret=-EINVAL;goto fail;}
 }
 if(!(ports[2].dev->priv_flags&IFF_EBRIDGE)){ret=-EINVAL;goto fail;}
 owner=READ_ONCE(((struct stmmac_priv *)netdev_priv(ports[0].dev))->dp_owner);
 if(!owner){ret=-ENODEV;goto fail;}
 /* RTNL excludes another detach; wait out its old TX readers before
  * reusing the static copied net_device_ops storage. */
 synchronize_net();
 original_ops=ports[0].dev->netdev_ops;
 if(original_ops==&tso_ops){ret=-EUCLEAN;goto fail;}
 tso_ops=*original_ops;tso_ops.ndo_features_check=tso_features_check;
 atomic64_set(&gso_packets,0);atomic64_set(&gso_bytes,0);
 WRITE_ONCE(enabled,true);WRITE_ONCE(ports[0].dev->netdev_ops,&tso_ops);
 for(i=0;i<ARRAY_SIZE(ports);i++){
  struct saved_port *p=&ports[i];struct net_device *d=p->dev;
  if(!p->route_only){
   d->features|=TSO_MASK;d->hw_features|=TSO_MASK;
   d->vlan_features|=TSO_MASK;d->wanted_features|=TSO_MASK;
  }
  WRITE_ONCE(d->gso_ipv4_max_size,min_t(unsigned int,p->ipv4_max,32768));
  netdev_update_features(d);
  if(!(d->features&NETIF_F_TSO)){ret=-EOPNOTSUPP;restore_rtnl();return ret;}
 }
 if(seconds)schedule_delayed_work(&rollback_work,msecs_to_jiffies(seconds*1000));
 pr_info("mf297d-host-tso: IPv4 TSO enabled on eth0/lan1; bridge=%s max=32768 rollback=%u\n",bridge_name,seconds);
 return 0;
fail:
 for(i=0;i<ARRAY_SIZE(ports);i++)ports[i].dev=NULL;
 return ret;
}

static void rollback_fn(struct work_struct *work)
{
 rtnl_lock();restore_rtnl();rtnl_unlock();
}
static int set_enable(const char *value,const struct kernel_param *kp)
{
 bool want;int ret=kstrtobool(value,&want);
 if(ret)return ret;
 if(!ready)return want ? -EPERM : 0;
 if(want && READ_ONCE(enabled))return 0;
 cancel_delayed_work_sync(&rollback_work);
 /* Old ndo callbacks must finish before the copied ops can be reused. */
 synchronize_net();
 rtnl_lock();
 if(want)ret=attach_rtnl();else restore_rtnl();
 rtnl_unlock();
 if(!want)synchronize_net();
 return ret;
}
static const struct kernel_param_ops enable_ops={.set=set_enable,.get=param_get_bool};
module_param_cb(enable,&enable_ops,&enabled,0600);
static int get_counter(char *buffer,const struct kernel_param *kp)
{
 return scnprintf(buffer,PAGE_SIZE,"%lld\n",(long long)atomic64_read(kp->arg));
}
static const struct kernel_param_ops counter_ops={.get=get_counter};
module_param_cb(gso_packets,&counter_ops,&gso_packets,0444);
module_param_cb(gso_bytes,&counter_ops,&gso_bytes,0444);

static int netdev_event(struct notifier_block *nb,unsigned long event,void *ptr)
{
 struct net_device *d=netdev_notifier_info_to_dev(ptr);unsigned int i;
 if(event!=NETDEV_UNREGISTER || !enabled)return NOTIFY_DONE;
 ASSERT_RTNL();
 for(i=0;i<ARRAY_SIZE(ports);i++)if(ports[i].dev==d){restore_rtnl();break;}
 return NOTIFY_DONE;
}
static struct notifier_block notifier={.notifier_call=netdev_event};
static int __init host_tso_init(void)
{
 int ret;
 if(!of_machine_is_compatible("zte,mf297d"))return -ENODEV;
 if(seconds>30 || !bridge_name || strnlen(bridge_name,IFNAMSIZ)>=IFNAMSIZ)return -EINVAL;
 ports[2].name=bridge_name;
 ret=register_netdevice_notifier(&notifier);if(ret)return ret;
 ready=true;pr_info("mf297d-host-tso: loaded inactive; rollback=%u\n",seconds);
 return 0;
}
static void __exit host_tso_exit(void)
{
 ready=false;cancel_delayed_work_sync(&rollback_work);
 rtnl_lock();restore_rtnl();rtnl_unlock();
 unregister_netdevice_notifier(&notifier);synchronize_net();
}
module_init(host_tso_init);module_exit(host_tso_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("MF297D NSS-owned IPv4 host TCP segmentation companion");
