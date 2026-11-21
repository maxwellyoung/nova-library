// SPDX-License-Identifier: GPL-3.0-or-later
#include "SaveCopyPictureProvider.h"
#ifdef QT_QUICK_LIB
#include <QImage>
#include <QMutexLocker>
namespace library {
QImage SaveCopyPictureProvider::requestImage(const QString& id,QSize* size,const QSize& requested) {
    QByteArray bytes;
    {QMutexLocker lock(&m_data->mutex);if(id!=m_data->token)return {};bytes=m_data->bytes;}
    auto image=QImage::fromData(bytes,"PNG");
    if(size)*size=image.size();
    if(!image.isNull() && requested.isValid() && (image.width()>requested.width() || image.height()>requested.height()))
        image=image.scaled(requested,Qt::KeepAspectRatio,Qt::SmoothTransformation);
    return image;
}
}
#endif
